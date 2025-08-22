from app.analysis.stocks import quarter_analysis
from dotenv import load_dotenv
from google import genai
import pandas as pd
import os
import re


class AnalystAgent:
    """
    An AI-powered analyst agent that interprets 13F data to generate strategic insights.
    It uses only the provided database and its internal knowledge to explain patterns.
    """
    def __init__(self, quarter):
        load_dotenv()
        self.client = genai.Client()
        self.model = 'gemini-2.5-flash'
        self.quarter = quarter
        
        print(f"Initializing Analyst Agent for quarter {self.quarter}...")
        self.analysis_df = quarter_analysis(self.quarter)


    def _get_ai_scores(self, stocks: list[dict]) -> dict:
        """
        Uses the LLM to categorize stocks into industries and generate AI-based scores.
        Accepts a list of dicts, where each dict is {'Ticker': str, 'Company': str}.
        """
        print("Categorizing stocks into industries and getting AI scores...")
        
        stocks_to_analyze_str = "\n".join([f"- {s['Ticker']} ({s['Company']})" for s in stocks])

        prompt = f"""
ROLE: You are a senior equity research analyst with 15+ years of experience in sector analysis and risk assessment.

TASK: Analyze the following stocks (Ticker and Company Name) and provide precise industry classification and quantitative scores.

STOCKS TO ANALYZE:
{stocks_to_analyze_str}

REQUIRED OUTPUT FORMAT (JSON only, no other text):
{{
  "TICKER": {{
    "sub_industry": "GICS Sub-Industry Name",
    "momentum_score": integer_1_to_100,
    "low_volatility_score": integer_1_to_100,
    "risk_score": integer_1_to_100
  }}
}}

SCORING CRITERIA:

1. SUB_INDUSTRY: Use exact GICS Sub-Industry classifications (e.g., "Application Software", "Biotechnology", "Integrated Oil & Gas")

2. MOMENTUM_SCORE (1-100):
   - 90-100: Sectors with explosive growth (AI, EVs, cybersecurity)
   - 70-89: Strong secular trends (cloud, healthcare tech)
   - 50-69: Steady growth sectors (consumer staples, utilities)
   - 30-49: Cyclical recovery sectors (travel, retail)
   - 1-29: Declining/disrupted sectors (legacy media, coal)

3. LOW_VOLATILITY_SCORE (1-100):
   - 90-100: Utilities, REITs, defensive consumer goods
   - 70-89: Large cap pharma, telecom, food/beverage
   - 50-69: Diversified industrials, banks
   - 30-49: Technology hardware, materials
   - 1-29: Biotechnology, small cap growth, crypto-related

4. RISK_SCORE (1-100):
   - 90-100: Pre-revenue biotech, highly leveraged, regulatory risk
   - 70-89: High growth tech, emerging markets, commodity cyclicals
   - 50-69: Established growth companies, mid-cap industrials
   - 30-49: Large cap tech, diversified healthcare
   - 1-29: Utilities, consumer staples, dividend aristocrats

VALIDATION EXAMPLES:
- NVDA (NVIDIA Corp): {{"sub_industry": "Semiconductors", "momentum_score": 95, "low_volatility_score": 25, "risk_score": 65}}
- JNJ (Johnson & Johnson): {{"sub_industry": "Pharmaceuticals", "momentum_score": 60, "low_volatility_score": 85, "risk_score": 25}}
- TSLA (Tesla, Inc.): {{"sub_industry": "Automobile Manufacturers", "momentum_score": 85, "low_volatility_score": 15, "risk_score": 80}}

OUTPUT (JSON only):"""

        try:
            print("Sending request to Google AI API for thematic scores...")
            response = self.client.models.generate_content(
                model=self.model,
                contents=prompt
            )
            
            import json
            # More robust JSON extraction
            response_text = response.text.strip()
            
            # Remove markdown code blocks if present
            if response_text.startswith('```'):
                response_text = re.sub(r'^```(?:json)?\s*\n', '', response_text)
                response_text = re.sub(r'\n```$', '', response_text)
            
            json_match = re.search(r'\{.*\}', response_text, re.DOTALL)
            
            if not json_match:
                print(f"Warning: Could not find JSON in response: {response_text[:200]}...")
                return {}

            json_string = json_match.group(0)
            parsed_data = json.loads(json_string)
            
            # Validate the structure
            for ticker, data in parsed_data.items():
                required_keys = ['sub_industry', 'momentum_score', 'low_volatility_score', 'risk_score']
                if not all(key in data for key in required_keys):
                    print(f"Warning: Missing required keys for {ticker}")
                    return {}
            
            print(f"Successfully parsed AI scores for {len(parsed_data)} tickers")
            return parsed_data

        except Exception as e:
            print(f"Could not get AI scores from LLM: {e}")
            return {}

    def _get_promise_score_weights(self) -> dict:
        """
        Uses the LLM to determine the optimal weights for calculating the Promise Score.
        """
        print("Asking AI for Promise Score weighting strategy...")

        prompt = f"""
ROLE: You are a quantitative portfolio manager specializing in 13F analysis and institutional flow strategies.

CONTEXT: Quarter {self.quarter} - Analyzing institutional fund movements to identify emerging opportunities.

TASK: Design optimal weights for a "Promise Score" algorithm that identifies stocks with the highest institutional conviction and momentum.

AVAILABLE METRICS:
• Total_Value: Total dollar value of the stock held by all institutions (measures overall institutional ownership and popularity).
• Total_Delta_Value: Net dollar flow across all institutions (measures raw capital allocation).
• Total_Weighted_Delta_Pct: Sum of percentage portfolio increases by buyers (measures conviction intensity).
• Max_Portfolio_Pct: Largest single fund allocation to the stock (measures individual conviction).
• Buyer_Count: Number of funds increasing positions (measures buying breadth).
• Seller_Count: Number of funds decreasing positions (measures selling pressure).
• Close_Count: Number of funds that completely sold out of their position (strong negative signal).
• Holder_Count: Total number of funds holding the stock (measures popularity/consensus).
• New_Holder_Count: Number of funds initiating new positions (measures emerging interest).
• Net_Buyers: Buyer_Count - Seller_Count (measures net institutional sentiment).
• Buyer_Seller_Ratio: Buyer_Count / Seller_Count. A high ratio indicates strong buying pressure. A value of 'inf' (infinity) signifies there are buyers but zero sellers from the previous quarter. This is a powerful signal for new interest.
• Delta: Percentage change in total value held by institutions. A value of 'inf' (infinity) also indicates a new position that wasn't held in the previous quarter by any hedge fund.

WEIGHTING PHILOSOPHY:
Focus on metrics that predict future outperformance:
- High-conviction moves (large % allocations) over raw dollar amounts.
- New institutional interest over existing holdings. Metrics like `Buyer_Seller_Ratio` and `Delta` being infinite are strong indicators of new, potentially high-momentum stocks (like recent IPOs).
- Quality of buyers over quantity.
- Forward-looking momentum indicators.
- CAUTION: `Buyer_Seller_Ratio` and `Delta` can be infinite, while `New_Holder_Count` is often very high especially for recent IPOs. Balance these powerful but potentially noisy signals to avoid overweighting IPOs which have no particular need to be identified using this heuristic.

CONSTRAINTS:
- Weights must sum to EXACTLY 1.
- `Seller_Count` and `Close_Count` can only have a zero or negative weight.

OUTPUT REQUIREMENTS:
Return ONLY a valid JSON object with metric names as keys and weights as values.
Weights must be decimal numbers that sum to 1.0.

EXAMPLE FORMATS:
{{"Total_Delta_Value": 0.4, "Total_Weighted_Delta_Pct": 0.35, "Max_Portfolio_Pct": 0.25}}

OR

{{"New_Holder_Count": 0.3, "Net_Buyers": 0.25, "Total_Weighted_Delta_Pct": 0.2, "Max_Portfolio_Pct": 0.15, "Buyer_Count": 0.1}}

OUTPUT (JSON only):"""

        try:
            response = self.client.models.generate_content(
                model=self.model,
                contents=prompt
            )
            response_text = response.text.strip()
            
            # Clean response
            if response_text.startswith('```'):
                response_text = re.sub(r'^```(?:json)?\s*\n', '', response_text)
                response_text = re.sub(r'\n```$', '', response_text)
            
            import json
            json_match = re.search(r'\{.*\}', response_text, re.DOTALL)
            
            if not json_match:
                print(f"ERROR: No JSON found in weights response from AI.")
                return {}
            
            json_string = json_match.group(0)
            parsed_weights = json.loads(json_string)
                  
            # Validation
            if not isinstance(parsed_weights, dict) or not parsed_weights:
                print("ERROR: AI returned an invalid weights structure.")
                return {}

            total_weight = sum(parsed_weights.values())
            if not (0.95 <= total_weight <= 1.05):  # Allow small errors
                print(f"ERROR: AI returned weights that sum to {total_weight:.3f}, not 1.0.")
                return {}

            # Validate that metrics exist in our analysis
            available_metrics = ['Total_Value', 'Total_Delta_Value', 'Total_Weighted_Delta_Pct', 'Max_Portfolio_Pct', 'Buyer_Count', 'Seller_Count', 'Holder_Count', 'New_Holder_Count', 'Net_Buyers', 'Close_Count', 'Buyer_Seller_Ratio', 'Delta']

            invalid_metrics = [m for m in parsed_weights.keys() if m not in available_metrics]
            if invalid_metrics:
                print(f"ERROR: AI Agent returned invalid metrics: {invalid_metrics}.")
                return {}

            print(f"AI Agent selected weights: {parsed_weights} (sum: {total_weight:.3f})")
            return parsed_weights

        except Exception as e:
            print(f"ERROR: Failed to get weights from AI Agent: {e}.")
            return {}


    def generate_scored_list(self, top_n=30):
        """
        Generates a scored and ranked list of the most promising stocks based on a heuristic model.
        """
        df = self.analysis_df.copy()

        # Let the LLM define the weights for the Promise score
        promise_weights = self._get_promise_score_weights()

        if not promise_weights:
            print("Error: Could not determine promise score weights.")
            return pd.DataFrame()

        df['Promise_Score'] = 0.0

        # Calculate percentile ranks and the weighted score dynamically
        for metric, weight in promise_weights.items():
            if metric in df.columns:
                rank_col = f'{metric}_rank'
                df[rank_col] = df[metric].rank(pct=True)
                df['Promise_Score'] += df[rank_col] * weight
            else:
                print(f"Warning: Metric '{metric}' suggested by AI not found in analysis data. Skipping.")

        df['Promise_Score'] *= 100

        suggestions_df = df.sort_values(by='Promise_Score', ascending=False).head(top_n)

        # Get thematic momentum scores for the top N stocks
        top_stocks = suggestions_df[['Ticker', 'Company']].to_dict('records')
        if top_stocks:
            ai_scores_data = self._get_ai_scores(top_stocks)
            # Map the nested dictionary to columns
            suggestions_df['Industry'] = suggestions_df['Ticker'].map(lambda t: ai_scores_data.get(t, {}).get('sub_industry', 'N/A'))
            suggestions_df['Risk_Score'] = suggestions_df['Ticker'].map(lambda t: ai_scores_data.get(t, {}).get('risk_score', 0))
            suggestions_df['Momentum_Score'] = suggestions_df['Ticker'].map(lambda t: ai_scores_data.get(t, {}).get('momentum_score', 0))
            suggestions_df['Low_Volatility_Score'] = suggestions_df['Ticker'].map(lambda t: ai_scores_data.get(t, {}).get('low_volatility_score', 0))
        else:
            suggestions_df['Industry'] = 'N/A'
            suggestions_df['Risk_Score'] = 0
            suggestions_df['Momentum_Score'] = 0
            suggestions_df['Low_Volatility_Score'] = 0

        return suggestions_df
