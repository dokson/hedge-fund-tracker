def quantivative_scores_prompt(stocks: list[dict], filing_date: str) -> str:
    """
    Build prompt for getting AI scores for stocks.
    """
    stocks_str = "\n".join([f"- {s['Ticker']} ({s['Company']})" for s in stocks])
    
    return f"""
ROLE: You are a senior equity research analyst with 15+ years of experience in sector analysis, risk assessment, and price action analysis. You have access to real-time and historical market data.

TASK: For the following stocks, provide precise industry classification and quantitative scores. A key score is the "Growth Potential", which you must calculate.

REFERENCE DATE FOR GROWTH POTENTIAL: {filing_date}

STOCKS TO ANALYZE:
{stocks_str}

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
    1. For each stock, calculate its percentage price change from the reference date ({filing_date}) to the present day.
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
