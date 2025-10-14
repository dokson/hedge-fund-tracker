def quantivative_scores_prompt(stocks: list[dict], filing_date: str) -> str:
    """
    Build prompt for getting AI scores for stocks.
    """
    stocks_str = "\n".join([f"- {s['Ticker']} ({s['Company']})" for s in stocks])
    
    return f"""
# ROLE
You are a senior equity research analyst with over 30 years of experience specializing in sector analysis, risk assessment, and price action analysis. You have access to real-time and historical market data.

Begin with a concise checklist (3-7 bullets) of what you will do for each stock; keep checklist items conceptual, not implementation-level.

# TASK
For each stock listed, provide an accurate industry classification and quantified scores according to the criteria below.
You must calculate the "Growth Potential" score as described.

REFERENCE DATE FOR GROWTH POTENTIAL: {filing_date}

STOCKS TO ANALYZE:
{stocks_str}

REQUIRED OUTPUT FORMAT (JSON only; do not include additional text):
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

2. MOMENTUM_SCORE (1–100):
   - 90-100: Sectors with explosive growth (AI, EVs, cybersecurity)
   - 70-89: Strong secular trends (cloud, healthcare tech)
   - 50-69: Steady growth sectors (consumer staples, utilities)
   - 30-49: Cyclical recovery sectors (travel, retail)
   - 1-29: Declining/disrupted sectors (legacy media, coal)

3. LOW_VOLATILITY_SCORE (1–100):
   - 90-100: Utilities, REITs, defensive consumer goods
   - 70-89: Large cap pharma, telecom, food/beverage
   - 50-69: Diversified industrials, banks
   - 30-49: Technology hardware, materials
   - 1-29: Biotechnology, small cap growth, crypto-related

4. RISK_SCORE (1–100):
   - 90-100: Pre-revenue biotech, highly leveraged, regulatory risk
   - 70-89: High growth tech, emerging markets, commodity cyclicals
   - 50-69: Established growth companies, mid-cap industrials
   - 30-49: Large cap tech, diversified healthcare
   - 1-29: Utilities, consumer staples, dividend aristocrats

5. GROWTH_POTENTIAL_SCORE (1–100):
   - **Objective**: Calculate a score representing untapped growth potential. The score is INVERSELY proportional to the stock's price performance since the reference date.
   - **Methodology**:
    1. For each stock, calculate its percentage price change from the reference date ({filing_date}) to the present day.
    2. Assign a score based on the following brackets. A high score means the stock has grown little or fallen, suggesting higher potential. A low score means the stock has already run up significantly.
   - **Scoring Brackets**:
       - 90-100: The stock has fallen significantly in price (>10% drop).
       - 70-89: The stock has fallen slightly or is flat (-10% to +5% change).
       - 50-69: The stock has seen modest growth (+5% to +20% change).
       - 30-49: The stock has grown significantly (+20% to +50% change).
       - 1-29: The stock has experienced explosive growth (>50% growth).

# VALIDATION EXAMPLES (assuming today is late July 2024 and reference date is 2024-06-30)
- NVDA (NVIDIA Corp): Price slightly down; {{"sub_industry": "Semiconductors", "momentum_score": 95, "low_volatility_score": 25, "risk_score": 65, "growth_potential_score": 75}}
- JNJ (Johnson & Johnson): Stable; {{"sub_industry": "Pharmaceuticals", "momentum_score": 60, "low_volatility_score": 85, "risk_score": 25, "growth_potential_score": 65}}
- LLY (Eli Lilly): Strong run-up; {{"sub_industry": "Pharmaceuticals", "momentum_score": 92, "low_volatility_score": 30, "risk_score": 55, "growth_potential_score": 20}}

# OUTPUT FORMAT
- Output must be a single JSON object with a top-level key for each TICKER, mapping to its results.
- All scores must be integers (1–100); round if necessary.
- For an invalid ticker, missing price data, or failed sub-industry classification, set ALL fields for that ticker to null.
- All fields must be present for each ticker (do not omit keys); use null for unavailable data.
- Example structure:
{{
   "NVDA": {{
      "sub_industry": "Semiconductors",
      "momentum_score": 95,
      "low_volatility_score": 25,
      "risk_score": 65,
      "growth_potential_score": 75
   }},
   "INVALID": {{
      "sub_industry": null,
      "momentum_score": null,
      "low_volatility_score": null,
      "risk_score": null,
      "growth_potential_score": null
   }}
}}
"""
