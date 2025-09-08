from app.ai.clients.base_client import AIClient
from app.ai.clients.google_client import GoogleAIClient
from app.ai.promise_score_validator import PromiseScoreValidator
from app.ai.prompts.promise_score_weights import promise_score_weights_prompt
from app.ai.prompts.quantitative_scores import quantivative_scores_prompt
from app.ai.response_parser import ResponseParser
from app.analysis.stocks import quarter_analysis
from app.utils.strings import get_quarter_date
import pandas as pd


class AnalystAgent:
    """
    AI-powered analyst agent that interprets 13F data to generate strategic insights
    """
    def __init__(self, quarter: str, ai_client: AIClient = None):
        self.quarter = quarter
        self.ai_client = ai_client or GoogleAIClient()
        self.filing_date = get_quarter_date(quarter)
        self.analysis_df = quarter_analysis(self.quarter)


    def _get_ai_scores(self, stocks: list[dict]) -> dict:
        """
        Uses the LLM to categorize stocks into industries and generate AI-based scores
        """
        print("Categorizing stocks into industries and getting AI scores...")
        prompt = quantivative_scores_prompt(stocks, self.filing_date)

        try:
            print(f"Sending request to AI ({self.ai_client.get_model_name()}) for thematic scores...")
            response_text = self.ai_client.generate_content(prompt)
            parsed_data = ResponseParser().extract_and_parse(response_text)
            
            # Validate the structure
            required_keys = ['sub_industry', 'momentum_score', 'low_volatility_score', 'risk_score', 'growth_potential_score']
            for ticker, data in parsed_data.items():
                if not all(key in data for key in required_keys):
                    print(f"⚠️\u3000Warning: Missing required keys for {ticker}")
                    return {}

            print(f"Successfully parsed AI scores for {len(parsed_data)} tickers")
            return parsed_data

        except Exception as e:
            print(f"❌ ERROR: Could not get scores from LLM: {e}")
            return {}


    def _get_promise_score_weights(self) -> dict:
        """
        Uses the LLM to determine the optimal weights for calculating the Promise Score
        """
        print(f"Sending request to AI ({self.ai_client.get_model_name()}) for Promise Score weighting strategy...")

        prompt = promise_score_weights_prompt(self.quarter)

        try:
            response_text = self.ai_client.generate_content(prompt)
            parsed_weights = ResponseParser().extract_and_parse(response_text)

            # Validation using PromiseScoreValidator
            if not PromiseScoreValidator().validate_weights(parsed_weights):
                total = sum(parsed_weights.values()) if parsed_weights else 0
                print(f"❌ ERROR: AI returned weights that sum to {total:.1f}, not 1.0.")
                return {}

            # Validate that metrics exist
            invalid_metrics = PromiseScoreValidator().validate_metrics(list(parsed_weights.keys()))
            if invalid_metrics:
                print(f"❌ ERROR: AI Agent returned invalid metrics: {invalid_metrics}.")
                return {}

            print(f"AI Agent selected weights: {parsed_weights} (sum: {sum(parsed_weights.values()):.2f})")
            return parsed_weights

        except Exception as e:
            print(f"❌ ERROR: Failed to get weights from AI Agent: {e}.")
            return {}


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
        
        # Let the LLM define the weights for the Promise score
        promise_weights = self._get_promise_score_weights()

        if not promise_weights:
            print("❌ ERROR: Could not determine promise score weights.")
            return pd.DataFrame()

        # Calculate Promise scores
        df = self._calculate_promise_scores(self.analysis_df, promise_weights)

        # Get top N stocks
        suggestions_df = df.sort_values(by='Promise_Score', ascending=False).head(top_n)

        # Get thematic momentum scores for the top N stocks
        top_stocks = suggestions_df[['Ticker', 'Company']].to_dict('records')
        if top_stocks:
            ai_scores_data = self._get_ai_scores(top_stocks)
            suggestions_df = self._add_ai_scores_to_df(suggestions_df, ai_scores_data)
        else:
            # Add empty columns if no stocks
            suggestions_df['Industry'] = None
            suggestions_df['Risk_Score'] = None
            suggestions_df['Momentum_Score'] = None
            suggestions_df['Low_Volatility_Score'] = None
            suggestions_df['Growth_Score'] = None

        return suggestions_df
