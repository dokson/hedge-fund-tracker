from app.analysis.stocks import quarter_analysis
from app.utils.strings import get_quarter_date
from dotenv import load_dotenv
from google import genai
import pandas as pd
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
        self.filing_date = get_quarter_date(quarter)
        
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
ROLE: You are a senior equity research analyst with 15+ years of experience in sector analysis, risk assessment, and price action analysis. You have access to real-time and historical market data.

TASK: For the following stocks, provide precise industry classification and quantitative scores. A key score is the "Growth Potential", which you must calculate.

REFERENCE DATE FOR GROWTH POTENTIAL: {self.filing_date}

STOCKS TO ANALYZE:
{stocks_to_analyze_str}

REQUIRED OUTPUT FORMAT (JSON only, no other text):
{{
  "TICKER": {{
    "sub_industry": "GICS Sub-Industry Name",
    "momentum_score": integer_1_to_100,
    "low_volatility_score": integer_1_to_100,
    "risk_score": integer_1_to_100,
    "growth_potential_score": integer_1_to_100
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

5. GROWTH_POTENTIAL_SCORE (1-100):
   - **Objective**: Calculate a score representing untapped growth potential. The score is INVERSELY proportional to the stock's price performance since the reference date.
   - **Methodology**:
    1. For each stock, calculate its percentage price change from the reference date ({self.filing_date}) to the present day.
    2. Assign a score based on the following brackets. A high score means the stock has grown little or fallen, suggesting higher potential. A low score means the stock has already run up significantly.
   - **Scoring Brackets**:
       - 90-100: The stock has fallen significantly in price (>10% drop).
       - 70-89: The stock has fallen slightly or is flat (-10% to +5% change).
       - 50-69: The stock has seen modest growth (+5% to +20% change).
       - 30-49: The stock has grown significantly (+20% to +50% change).
       - 1-29: The stock has experienced explosive growth (>50% growth).

VALIDATION EXAMPLES (Illustrative, assuming today is late July 2024 and reference date is 2024-06-30):
- NVDA (NVIDIA Corp): Price has been volatile but might be slightly down since June 30. {{"sub_industry": "Semiconductors", "momentum_score": 95, "low_volatility_score": 25, "risk_score": 65, "growth_potential_score": 75}}
- JNJ (Johnson & Johnson): Stable stock, likely minor change. {{"sub_industry": "Pharmaceuticals", "momentum_score": 60, "low_volatility_score": 85, "risk_score": 25, "growth_potential_score": 65}}
- LLY (Eli Lilly): Has continued its strong run-up. {{"sub_industry": "Pharmaceuticals", "momentum_score": 92, "low_volatility_score": 30, "risk_score": 55, "growth_potential_score": 20}}

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
                required_keys = ['sub_industry', 'momentum_score', 'low_volatility_score', 'risk_score', 'growth_potential_score']
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
• Max_Portfolio_Pct: Largest single fund allocation to the stock (measures individual conviction).
• Buyer_Count: Number of funds increasing positions (measures buying breadth).
• Seller_Count: Number of funds decreasing positions (measures selling pressure).
• Close_Count: Number of funds that completely sold out of their position (strong negative signal).
• Holder_Count: Total number of funds holding the stock (measures popularity/consensus).
• New_Holder_Count: Number of funds initiating new positions (measures emerging interest).
• Net_Buyers: Buyer_Count - Seller_Count (measures net institutional sentiment).

WEIGHTING PHILOSOPHY:
Focus on metrics that predict future outperformance (considering data is only available from top world hedge funds):
- High-conviction moves.
- New institutional interest over existing holdings.
- Quantity of buyers over quantity of sellers.
- Forward-looking momentum indicators.
- CAUTION: `New_Holder_Count` can be very high especially for recent IPOs. Balance this powerful but potentially noisy signal to avoid overweighting IPOs which have no particular need to be identified using this heuristic.

CONSTRAINTS:
- Weights must sum to EXACTLY 1.
- `Seller_Count` and `Close_Count` can only have a zero or negative weight.

OUTPUT REQUIREMENTS:
Return ONLY a valid JSON object with metric names as keys and weights as values.
Weights must be decimal numbers that sum to 1.0.

EXAMPLE FORMATS:
{{"Total_Delta_Value": 0.4, "New_Holder_Count": 0.35, "Max_Portfolio_Pct": 0.25}}

OR

{{"New_Holder_Count": 0.3, "Net_Buyers": 0.25, "Close_Count": -0.2, "Max_Portfolio_Pct": 0.15, "Buyer_Count": 0.1}}

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
            available_metrics = ['Total_Value', 'Total_Delta_Value', 'Max_Portfolio_Pct', 'Buyer_Count', 'Seller_Count', 'Holder_Count', 'New_Holder_Count', 'Net_Buyers', 'Close_Count']

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
