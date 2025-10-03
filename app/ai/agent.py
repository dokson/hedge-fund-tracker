from app.ai.clients import AIClient
from app.ai.promise_score_validator import PromiseScoreValidator
from app.ai.prompts import promise_score_weights_prompt, quantivative_scores_prompt
from app.ai.response_parser import ResponseParser
from app.analysis.stocks import quarter_analysis
from app.utils.strings import get_quarter_date
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type, RetryError, wait_fixed
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
        wait=wait_exponential(multiplier=2),
        stop=stop_after_attempt(3),
        before_sleep=lambda rs: print(f"⚠️\u3000Warning: {rs.outcome.exception()}. Retrying in {rs.next_action.sleep:.0f}s...")
    )
    def _get_ai_scores(self, stocks: list[dict]) -> dict:
        """
        Uses the LLM to categorize stocks and generate AI scores.
        Retries with tenacity if the response is invalid.
        """
        prompt = quantivative_scores_prompt(stocks, self.filing_date)
        required_keys = ['sub_industry', 'momentum_score', 'low_volatility_score', 'risk_score', 'growth_potential_score']

        print(f"Sending request to AI ({self.ai_client.get_model_name()}) for thematic scores...")
        response_text = self.ai_client.generate_content(prompt)
        parsed_data = ResponseParser().extract_and_parse(response_text)

        if not parsed_data:
            raise InvalidAIResponseError("AI returned no data")

        if not all(all(key in data for key in required_keys) for data in parsed_data.values()):
            raise InvalidAIResponseError("AI response was missing required keys")

        print(f"Successfully parsed AI scores for {len(parsed_data)} tickers")
        return parsed_data


    @retry(
        retry=retry_if_exception_type(InvalidAIResponseError),
        wait=wait_fixed(1),
        stop=stop_after_attempt(7),
        before_sleep=lambda rs: print(f"⚠️\u3000Warning: {rs.outcome.exception()}. Retrying in {rs.next_action.sleep:.0f}s...")
    )
    def _get_promise_score_weights(self) -> dict:
        """
        Uses the LLM to determine the optimal weights for the Promise Score.
        Retries with tenacity if the weights or metrics are invalid.
        """
        print(f"Sending request to AI ({self.ai_client.get_model_name()}) for Promise Score weighting strategy...")
        prompt = promise_score_weights_prompt(self.quarter)

        response_text = self.ai_client.generate_content(prompt)
        parsed_weights = ResponseParser().extract_and_parse(response_text)

        total = sum(parsed_weights.values())
        
        if not PromiseScoreValidator.validate_weights(parsed_weights):
            raise InvalidAIResponseError(f"AI returned weights that sum to {total:.2f}, not 1.0")

        invalid_metrics = PromiseScoreValidator.validate_metrics(list(parsed_weights.keys()))
        if invalid_metrics:
            raise InvalidAIResponseError(f"AI returned invalid metrics: {invalid_metrics}")

        print(f"AI Agent selected weights: {parsed_weights} (sum: {total:.2f})")
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
                print(f"⚠️\u3000Warning: Metric '{metric}' suggested by AI not found in analysis data. Skipping.")

        df['Promise_Score'] *= 100
        return df


    def _add_ai_scores_to_df(self, df: pd.DataFrame, ai_scores_data: dict) -> pd.DataFrame:
        """
        Add AI scores to the dataframe
        """
        df = df.copy()
        df['Industry'] = df['Ticker'].map(lambda t: ai_scores_data.get(t, {}).get('sub_industry', 'N/A'))
        df['Risk_Score'] = df['Ticker'].map(lambda t: ai_scores_data.get(t, {}).get('risk_score', 0))
        df['Momentum_Score'] = df['Ticker'].map(lambda t: ai_scores_data.get(t, {}).get('momentum_score', 0))
        df['Low_Volatility_Score'] = df['Ticker'].map(lambda t: ai_scores_data.get(t, {}).get('low_volatility_score', 0))
        df['Growth_Score'] = df['Ticker'].map(lambda t: ai_scores_data.get(t, {}).get('growth_potential_score', 0))
        return df


    def generate_scored_list(self, top_n: int = None):
        """
        Generates a scored and ranked list of the most promising stocks based on a heuristic model
        """
        top_n = top_n or self.config.top_n_stocks
        
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

        # Get thematic momentum scores for the top N stocks
        top_stocks = suggestions_df[['Ticker', 'Company']].to_dict('records')
        if top_stocks:
            try:
                ai_scores_data = self._get_ai_scores(top_stocks)
                suggestions_df = self._add_ai_scores_to_df(suggestions_df, ai_scores_data)
            except RetryError as e:
                print(f"❌ ERROR: Failed to get valid AI scores after multiple attempts: {e.last_attempt.exception()}")
                return pd.DataFrame()

        else:
            # Add empty columns if no stocks
            suggestions_df['Industry'] = None
            suggestions_df['Risk_Score'] = None
            suggestions_df['Momentum_Score'] = None
            suggestions_df['Low_Volatility_Score'] = None
            suggestions_df['Growth_Score'] = None

        return suggestions_df
