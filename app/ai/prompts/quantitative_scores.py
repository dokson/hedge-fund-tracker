def quantitative_scores_prompt(stocks_toon: str, filing_date: str) -> str:
    """
    Build prompt for getting AI scores for stocks.
    """
    return f"""
# ROLE
You are a senior equity research analyst specializing in sector classification and risk assessment.

# TASK
For every stock in STOCKS TO ANALYZE, return its industry classification and a risk score.

# DATA YOU HAVE
For each stock you receive: company name, sector, filing date ({filing_date}), price at the filing date, current price, and the percentage change between the two. You have no other market data (no price history, no volume) beyond these fields.
Use those fields plus your general knowledge of the company. State only what you are confident about and NEVER invent a figure you were not given. If a company is unknown to you, score it from the supplied price change plus its sector and size, and stay near the middle of the band instead of guessing at an extreme.

# STOCKS TO ANALYZE
```toon
{stocks_toon}
```

# SCORING CRITERIA

1. INDUSTRY
   - The `industry` field you are given may be a broad SECTOR (e.g. "Technology"). Replace it with the specific Yahoo Finance INDUSTRY for the company (e.g. "Semiconductors", "Communication Equipment", "Asset Management").
   - If the ticker is an Exchange Traded Fund, set industry to "ETF".
   - If you do not know the company well enough to classify it, return the value you were given.

2. RISK_SCORE (1-100, HIGH IS BAD)
   - Assess the probability of PERMANENT capital loss: leverage, cash burn, customer or asset concentration, binary regulatory or clinical outcomes, going-concern doubt. This is a fundamental judgment, not a price judgment: do not raise it merely because the stock fell.
   - 90-100: speculative or distressed, high leverage, binary outcomes, extreme regulatory or competitive threats.
   - 70-89: high growth with high valuation risk, heavy exposure to cyclical downturns or disruption.
   - 50-69: moderate risk, established business model but sensitive to economic cycles or industry shifts.
   - 30-49: lower risk, strong balance sheet, diversified revenue, defensive characteristics.
   - 1-29: minimal risk, blue-chip quality, fortress balance sheet, predictable cash flows.

# CALIBRATION (illustrative profiles, not current readings of any company)
- High-growth semiconductor leader: risk 65.
- Defensive consumer staple: risk 20.
- Large diversified pharma: risk 40.

# OUTPUT FORMAT
Return a JSON object with a single field `stocks`: a list with one item per stock.
- Each item has `ticker` (spelled exactly as provided), `industry` (string), and `risk_score` (integer 1-100).
- Every ticker in the input MUST appear exactly once.
- Avoid clustering on multiples of 5: use the full integer range so the scores stay separable.
"""


def _score_field() -> dict:
    """
    An integer score on the 1-100 scale.
    """
    return {"type": "integer", "minimum": 1, "maximum": 100}


SCORES_SCHEMA: dict = {
    "type": "object",
    "properties": {
        "stocks": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "ticker": {"type": "string"},
                    "industry": {"type": "string"},
                    "risk_score": _score_field(),
                },
                "required": [
                    "ticker",
                    "industry",
                    "risk_score",
                ],
                "additionalProperties": False,
            },
        }
    },
    "required": ["stocks"],
    "additionalProperties": False,
}
