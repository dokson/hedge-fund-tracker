from app.ai.prompts.promise_score_weights import promise_score_weights_prompt
from app.ai.prompts.quantitative_scores import quantivative_scores_prompt
from app.analysis.stocks import quarter_analysis
from app.utils.strings import get_quarter_date
from dotenv import load_dotenv
from google import genai
from tenacity import retry, stop_after_attempt, wait_exponential
import json
import pandas as pd
import re


class AnalystAgent:
    """
    An AI-powered analyst agent that interprets 13F data to generate strategic insights.
    """
    def __init__(self, quarter):
        load_dotenv()
        self.client = genai.Client()
        self.model = 'gemini-2.5-flash'
        self.quarter = quarter
        self.filing_date = get_quarter_date(quarter)
        self.analysis_df = quarter_analysis(self.quarter)


    def _extract_json_from_response(self, response_text: str) -> dict:
        """
        Extract and parse JSON from LLM response.
        """
        try:
            # Clean response
            clean_text = response_text.strip()
            if clean_text.startswith('```'):
                clean_text = re.sub(r'^```(?:json)?\s*\n', '', clean_text)
                clean_text = re.sub(r'\n```$', '', clean_text)
            
            json_match = re.search(r'\{.*\}', clean_text, re.DOTALL)
            
            if not json_match:
                print(f"⚠️\u3000Warning: Could not find JSON in response: {response_text[:200]}...")
                return {}

            json_string = json_match.group(0)
            return json.loads(json_string)
            
        except Exception as e:
            print(f"❌ ERROR: Invalid JSON structure: {e}")
            return {}
        
    @retry(
        wait=wait_exponential(multiplier=2, min=1, max=3),
        stop=stop_after_attempt(3),
        before_sleep=lambda rs: print(f"Service unavailable, retrying in {rs.next_action.sleep:.2f}s... (Attempt #{rs.attempt_number})")
    )
    def _call_ai_api(self, prompt):
        """
        Calls the Google AI API with a given prompt and includes robust retry logic.
        """
        return self.client.models.generate_content(
            model=self.model,
            contents=prompt
        )

    def _get_ai_scores(self, stocks: list[dict]) -> dict:
        """
        Uses the LLM to categorize stocks into industries and generate AI-based scores.
        """
        print("Categorizing stocks into industries and getting AI scores...")
        
        prompt = quantivative_scores_prompt(stocks, self.filing_date)

        try:
            print(f"Sending request to Google AI ({self.model}) for thematic scores...")
            response = self._call_ai_api(prompt)
            parsed_data = self._extract_json_from_response(response.text)
            
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
        Uses the LLM to determine the optimal weights for calculating the Promise Score.
        """
        print(f"Sending request to Google AI ({self.model}) for Promise Score weighting strategy...")

        prompt = promise_score_weights_prompt(self.quarter)

        try:
            response = self._call_ai_api(prompt)
            parsed_weights = self._extract_json_from_response(response.text)

            # Validation
            if not isinstance(parsed_weights, dict) or not parsed_weights:
                print("❌ ERROR: AI returned an invalid weights structure.")
                return {}

            total_weight = sum(parsed_weights.values())
            if not (0.95 <= total_weight <= 1.05):  # Allow small errors
                print(f"❌ ERROR: AI returned weights that sum to {total_weight:.1f}, not 1.0.")
                return {}

            # Validate that metrics exist in our analysis
            available_metrics = ['Total_Value', 'Total_Delta_Value', 'Max_Portfolio_Pct', 'Buyer_Count', 'Seller_Count', 'Holder_Count', 'New_Holder_Count', 'Net_Buyers', 'Close_Count']

            invalid_metrics = [m for m in parsed_weights.keys() if m not in available_metrics]
            if invalid_metrics:
                print(f"❌ ERROR: AI Agent returned invalid metrics: {invalid_metrics}.")
                return {}

            print(f"AI Agent selected weights: {parsed_weights} (sum: {total_weight:.3f})")
            return parsed_weights

        except Exception as e:
            print(f"❌ ERROR: Failed to get weights from AI Agent: {e}.")
            return {}        


    def generate_scored_list(self, top_n=30):
        """
        Generates a scored and ranked list of the most promising stocks based on a heuristic model.
        """
        df = self.analysis_df.copy()

        # Let the LLM define the weights for the Promise score
        promise_weights = self._get_promise_score_weights()

        if not promise_weights:
            print("❌ ERROR: Could not determine promise score weights.")
            return pd.DataFrame()

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

        suggestions_df = df.sort_values(by='Promise_Score', ascending=False).head(top_n)

        # Get thematic momentum scores for the top N stocks
        top_stocks = suggestions_df[['Ticker', 'Company']].to_dict('records')
        if top_stocks:
            ai_scores_data = self._get_ai_scores(top_stocks)
            suggestions_df['Industry'] = suggestions_df['Ticker'].map(lambda t: ai_scores_data.get(t, {}).get('sub_industry', 'N/A'))
            suggestions_df['Risk_Score'] = suggestions_df['Ticker'].map(lambda t: ai_scores_data.get(t, {}).get('risk_score', 0))
            suggestions_df['Momentum_Score'] = suggestions_df['Ticker'].map(lambda t: ai_scores_data.get(t, {}).get('momentum_score', 0))
            suggestions_df['Low_Volatility_Score'] = suggestions_df['Ticker'].map(lambda t: ai_scores_data.get(t, {}).get('low_volatility_score', 0))
            suggestions_df['Growth_Score'] = suggestions_df['Ticker'].map(lambda t: ai_scores_data.get(t, {}).get('growth_potential_score', 0))
        else:
            suggestions_df['Industry'] = None
            suggestions_df['Risk_Score'] = None
            suggestions_df['Momentum_Score'] = None
            suggestions_df['Low_Volatility_Score'] = None
            suggestions_df['Growth_Score'] = None

        return suggestions_df
