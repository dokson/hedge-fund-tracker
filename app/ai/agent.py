from app.ai.clients import AIClient
from app.ai.promise_score_validator import PromiseScoreValidator
from app.ai.prompts import promise_score_weights_prompt, quantivative_scores_prompt, stock_due_diligence_prompt
from app.ai.response_parser import ResponseParser
from app.analysis.performance_evaluator import PerformanceEvaluator
from app.analysis.stocks import quarter_analysis, stock_analysis
from app.stocks.libraries import YFinance
from app.stocks.price_fetcher import PriceFetcher
from app.utils.strings import get_quarter_date
from datetime import date
from tenacity import retry, stop_after_attempt, retry_if_exception_type, RetryError, wait_fixed
from toon import encode
import pandas as pd


class InvalidAIResponseError(Exception):
    """
    Custom exception for invalid AI responses that should trigger a retry.
    """
    pass


class AnalystAgent:
    """
    AI-powered analyst agent that interprets 13F data to generate strategic insights
    """
    def __init__(self, quarter: str, ai_client: AIClient = None):
        self.quarter = quarter
        self.ai_client = ai_client
        self.filing_date = get_quarter_date(quarter)
        self.analysis_df = quarter_analysis(self.quarter)


    @retry(
        retry=retry_if_exception_type(InvalidAIResponseError),
        wait=wait_fixed(1),
        stop=stop_after_attempt(7),
        before_sleep=lambda rs: print(f"🚨 Warning: {rs.outcome.exception()}. Retrying in {rs.next_action.sleep:.0f}s...")
    )
    def _get_promise_score_weights(self) -> dict:
        """
        Uses the LLM to determine the optimal weights for the Promise Score.
        Retries with tenacity if the weights or metrics are invalid.
        """
        print(f"Sending request to AI ({self.ai_client.get_model_name()}) for Promise Score weighting strategy...")
        prompt = promise_score_weights_prompt(self.quarter)

        response_text = self.ai_client.generate_content(prompt)
        parsed_weights = ResponseParser().extract_and_decode_toon(response_text)
        total = sum(parsed_weights.values())

        if not PromiseScoreValidator.validate_weights(parsed_weights):
            raise InvalidAIResponseError(f"AI returned weights that sum to {total:.2f}, not 1.0")

        invalid_metrics = PromiseScoreValidator.validate_metrics(list(parsed_weights.keys()))
        if invalid_metrics:
            raise InvalidAIResponseError(f"AI returned invalid metrics: {invalid_metrics}")

        weights_str = "\n\t" + "\n\t".join([f"{k:<20} = {v:5.2f}" for k, v in parsed_weights.items()])
        print(f"✅ AI Agent selected weights (sum: {total:.2f}):{weights_str}")
        return parsed_weights


    def _calculate_promise_scores(self, df: pd.DataFrame, promise_weights: dict) -> pd.DataFrame:
        """
        Calculate Promise scores based on weights
        """
        df = df.copy()
        df['Promise_Score'] = 0.0

        # Calculate percentile ranks and the weighted score dynamically
        for metric, weight in promise_weights.items():
            if metric in df.columns:
                rank_col = f'{metric}_rank'
                df[rank_col] = df[metric].rank(pct=True)
                df['Promise_Score'] += df[rank_col] * weight
            else:
                print(f"🚨 Warning: Metric '{metric}' suggested by AI not found in analysis data. Skipping.")

        df['Promise_Score'] *= 100
        return df


    @retry(
        retry=retry_if_exception_type(InvalidAIResponseError),
        wait=wait_fixed(1),
        stop=stop_after_attempt(5),
        before_sleep=lambda rs: print(f"🚨 Warning: {rs.outcome.exception()}. Retrying in {rs.next_action.sleep:.0f}s...")
    )
    def _get_ai_scores(self, stocks_context: list[dict]) -> dict:
        """
        Uses the LLM to categorize stocks and generate thematic AI scores.
        Retries with tenacity if the response is invalid.
        """
        prompt = quantivative_scores_prompt(encode(stocks_context), self.filing_date)
        required_keys = ['momentum_score', 'low_volatility_score', 'risk_score']

        print(f"Sending request to AI ({self.ai_client.get_model_name()}) for thematic scores...")
        response_text = self.ai_client.generate_content(prompt)
        parsed_data = ResponseParser().extract_and_decode_toon(response_text)

        if not parsed_data:
            raise InvalidAIResponseError("AI returned no data")

        if not all(all(key in data for key in required_keys) for data in parsed_data.values()):
            raise InvalidAIResponseError("AI response was missing required keys")

        print(f"✅ Successfully parsed AI scores for {len(parsed_data)} tickers")
        return parsed_data


    def generate_scored_list(self, top_n: int) -> pd.DataFrame:
        """
        Generates a scored and ranked list of the most promising stocks based on a heuristic model
        """
        try:
            # Let the LLM define the weights for the Promise score
            promise_weights = self._get_promise_score_weights()
        except RetryError as e:
            print(f"❌ ERROR: Failed to get valid promise score weights after multiple attempts: {e.last_attempt.exception()}")
            return pd.DataFrame()

        # Calculate Promise scores
        df = self._calculate_promise_scores(self.analysis_df, promise_weights)

        # Get top N stocks
        suggestions_df = df.sort_values(by='Promise_Score', ascending=False).head(top_n)

        # Get top N tickers
        tickers = suggestions_df['Ticker'].tolist()
        if not tickers:
            return suggestions_df

        # 1. Get industry and current price programmatically from YFinance
        print(f"🔍 Fetching programmatic data for {len(tickers)} tickers from YFinance...")
        stocks_info = YFinance.get_stocks_info(tickers)

        # 2. Calculate Growth scores autonomously
        autonomous_scores = {}
        for ticker in tickers:
            info = stocks_info.get(ticker, {})
            current_price = info.get('price')
            industry = info.get('sector')
            
            if current_price:
                # Get historical price
                filing_price = PriceFetcher.get_avg_price(ticker, date.fromisoformat(self.filing_date))
                
                if filing_price:
                    pct_change = ((current_price - filing_price) / filing_price) * 100
                    growth_score = PerformanceEvaluator.calculate_growth_score(pct_change)
            
            autonomous_scores[ticker] = {
                'Industry': industry or 'N/A',
                'Growth_Score': growth_score if growth_score else "N/A",
                'Current_Price': f"${current_price:,.2f}" if current_price else "N/A",
                'Filing_Price': f"${filing_price:,.2f}" if filing_price else "N/A",
                'Pct_Change': f"{pct_change:+.2f}%" if current_price and filing_price else "N/A"
            }

        # 3. Get LLM scores (Momentum, Volatility, Risk)
        stocks_context = []
        for ticker in tickers:
            stocks_context.append({
                'ticker': ticker,
                'company': suggestions_df[suggestions_df['Ticker'] == ticker]['Company'].iloc[0],
                'industry': autonomous_scores[ticker]['Industry'],
                'filing_date': self.filing_date,
                'filing_price': autonomous_scores[ticker]['Filing_Price'],
                'current_price': autonomous_scores[ticker]['Current_Price'],
                'price_change_since_filing': autonomous_scores[ticker]['Pct_Change']
            })

        try:
            ai_scores_data = self._get_ai_scores(stocks_context)
            
            # 4. Combine and update dataframe
            suggestions_df = suggestions_df.copy()
            suggestions_df['Industry'] = suggestions_df['Ticker'].map(lambda t: ai_scores_data.get(t, {}).get('industry') or autonomous_scores.get(t, {}).get('Industry', 'N/A'))
            suggestions_df['Growth_Score'] = suggestions_df['Ticker'].map(lambda t: autonomous_scores.get(t, {}).get('Growth_Score', 0))
            suggestions_df['Risk_Score'] = suggestions_df['Ticker'].map(lambda t: ai_scores_data.get(t, {}).get('risk_score', 0))
            suggestions_df['Momentum_Score'] = suggestions_df['Ticker'].map(lambda t: ai_scores_data.get(t, {}).get('momentum_score', 0))
            suggestions_df['Low_Volatility_Score'] = suggestions_df['Ticker'].map(lambda t: ai_scores_data.get(t, {}).get('low_volatility_score', 0))

        except RetryError as e:
            print(f"❌ ERROR: Failed to get valid AI scores after multiple attempts: {e.last_attempt.exception()}")
            # Set defaults if AI fails
            suggestions_df['Industry'] = suggestions_df['Ticker'].map(lambda t: autonomous_scores.get(t, {}).get('Industry', 'N/A'))
            suggestions_df['Growth_Score'] = suggestions_df['Ticker'].map(lambda t: autonomous_scores.get(t, {}).get('Growth_Score', 0))
            suggestions_df['Risk_Score'] = 0
            suggestions_df['Momentum_Score'] = 0
            suggestions_df['Low_Volatility_Score'] = 0

        return suggestions_df


    @retry(
        retry=retry_if_exception_type(InvalidAIResponseError),
        wait=wait_fixed(1),
        stop=stop_after_attempt(5),
        before_sleep=lambda rs: print(f"🚨 Warning: {rs.outcome.exception()}. Retrying in {rs.next_action.sleep:.0f}s...")
    )
    def run_stock_due_diligence(self, ticker: str) -> dict:
        """
        Performs AI-powered due diligence on a single stock.

        Args:
            ticker (str): The stock ticker to analyze.

        Returns:
            dict: A dictionary containing the AI's analysis, or an empty dict if an error occurs.
        """
        print(f"Gathering institutional data for {ticker} for quarter {self.quarter}...")
        stock_df = stock_analysis(ticker, self.quarter)

        if stock_df.empty:
            print(f"❌ No data found for ticker {ticker} in quarter {self.quarter}.")
            return {}

        current_price = PriceFetcher.get_current_price(ticker)
        if current_price is None:
            print(f"❌ Could not fetch current price for {ticker}. Aborting due diligence.")
            return {}
        print(f"💲 Current price for {ticker}: ${current_price:,.2f}")

        filing_date_price = PriceFetcher.get_avg_price(ticker, date.fromisoformat(self.filing_date))
        price_delta_pct = None
        if filing_date_price:
            print(f"💲 Price on filing date ({self.filing_date}): ${filing_date_price:,.2f}")
            price_delta_pct = ((current_price - filing_date_price) / filing_date_price) * 100

        total_value = stock_df['Value'].sum()
        total_delta_value = stock_df['Delta_Value'].sum()
        previous_total_value = total_value - total_delta_value
        delta_pct = total_delta_value / previous_total_value * 100 if previous_total_value != 0 else 0

        # Get summary metrics for this ticker
        summary_row = self.analysis_df[self.analysis_df['Ticker'] == ticker].iloc[0] if not self.analysis_df[self.analysis_df['Ticker'] == ticker].empty else None

        stock_data = {
            "ticker": ticker,
            "company": stock_df['Company'].iloc[0],
            "filing_date": self.filing_date,
            "current_date": date.today().isoformat(),
            "filing_date_price": f"${filing_date_price:,.2f}" if filing_date_price else "N/A",
            "current_price": f"${current_price:,.2f}",
            "price_delta_percentage": f"{price_delta_pct:+.2f}%" if price_delta_pct is not None else "N/A",
            "institutional_activity": {
                "total_value_held": f"${total_value:,.0f}",
                "net_change_in_value": f"${total_delta_value:,.0f}",
                "delta_percentage": f"{delta_pct:+.2f}%",
                "buyers": int((stock_df['Delta_Value'] > 0).sum()),
                "sellers": int((stock_df['Delta_Value'] < 0).sum()),
                "new_positions": int((stock_df['Delta'].str.startswith('NEW')).sum()),
                "closed_positions": int((stock_df['Delta'] == 'CLOSE').sum()),
                "high_conviction_new_entries": int(summary_row['High_Conviction_Count']) if summary_row is not None else 0,
                "ownership_delta_avg": f"{summary_row['Ownership_Delta_Avg']:+.2f}%" if summary_row is not None else "0.00%",
                "portfolio_concentration_avg": f"{summary_row['Portfolio_Concentration_Avg']:.2f}%" if summary_row is not None else "0.00%"
            }
        }
        stock_context_toon = encode(stock_data)

        print(f"Sending request to AI ({self.ai_client.get_model_name()}) for due diligence on {ticker}...")
        prompt = stock_due_diligence_prompt(stock_context_toon)
        response_text = self.ai_client.generate_content(prompt)
        parsed_data = ResponseParser().extract_and_decode_toon(response_text)

        if not parsed_data:
            raise InvalidAIResponseError("AI returned an empty or invalid TOON structure")

        parsed_data['current_price'] = current_price

        return parsed_data
