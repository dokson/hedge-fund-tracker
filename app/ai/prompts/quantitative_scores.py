def quantivative_scores_prompt(stocks_toon: str, filing_date: str) -> str:
    """
    Build prompt for getting AI scores for stocks.
    """
    return f"""
# ROLE
You are a senior equity research analyst specializing in sector classification, risk assessment and price action.

# TASK
For every stock in STOCKS TO ANALYZE, return its industry classification and three scores: momentum, low volatility and risk.

# DATA YOU HAVE
For each stock you receive: company name, sector, filing date ({filing_date}), price at the filing date, current price, and the percentage change between the two. You have no other market data (no price history, no volume, no volatility series) beyond these fields.
Use those fields plus your general knowledge of the company. State only what you are confident about and NEVER invent a figure you were not given. If a company is unknown to you, score it from the supplied price change plus its sector and size, and stay near the middle of each band instead of guessing at an extreme.

# STOCKS TO ANALYZE
```toon
{stocks_toon}
```

# SCORING CRITERIA

1. INDUSTRY
   - The `industry` field you are given may be a broad SECTOR (e.g. "Technology"). Replace it with the specific Yahoo Finance INDUSTRY for the company (e.g. "Semiconductors", "Communication Equipment", "Asset Management").
   - If the ticker is an Exchange Traded Fund, set industry to "ETF".
   - If you do not know the company well enough to classify it, return the value you were given.

2. MOMENTUM_SCORE (1-100, HIGH IS GOOD)
   - Rank the strength of the price trend RELATIVE TO THE OTHER STOCKS IN THIS LIST, all measured over the same window, then map it onto these bands.
   - 90-100: explosive upward momentum, the strongest names in the list, heavy buying pressure.
   - 70-89: solid uptrend, consistently ahead of the rest of the list.
   - 50-69: moderate momentum, recovery or steady consolidation with a slight upward bias.
   - 30-49: weakening trend, sideways, or behind the rest of the list.
   - 1-29: negative momentum, strong downtrend, heavy selling pressure.

3. LOW_VOLATILITY_SCORE (1-100, HIGH IS GOOD)
   - Score LONG-RUN price stability: realized volatility and beta, not the sector and not the single move shown here. A large drawdown in one quarter does not by itself make a low-beta company volatile, and a micro-cap with a flat quarter is still high-beta. The supplied price change is a weak, secondary input.
   - 90-100: extremely stable price action, very low beta, minimal long-term drawdowns.
   - 70-89: consistent trends, moderate volatility, resilient in market downturns.
   - 50-69: balanced volatility, typical of consolidated large caps.
   - 30-49: frequent wide swings, higher beta, significant historical fluctuations.
   - 1-29: high-beta, extreme spikes and drops, speculative price action.

4. RISK_SCORE (1-100, HIGH IS BAD - the direction is inverted relative to the two scores above)
   - Assess the probability of PERMANENT capital loss: leverage, cash burn, customer or asset concentration, binary regulatory or clinical outcomes, going-concern doubt. This is a fundamental judgment, not a price judgment: do not raise it merely because the stock fell.
   - 90-100: speculative or distressed, high leverage, binary outcomes, extreme regulatory or competitive threats.
   - 70-89: high growth with high valuation risk, heavy exposure to cyclical downturns or disruption.
   - 50-69: moderate risk, established business model but sensitive to economic cycles or industry shifts.
   - 30-49: lower risk, strong balance sheet, diversified revenue, defensive characteristics.
   - 1-29: minimal risk, blue-chip quality, fortress balance sheet, predictable cash flows.

# CALIBRATION (illustrative profiles, not current readings of any company)
- High-growth semiconductor leader in a strong uptrend: momentum 95, low_volatility 25, risk 65.
- Defensive consumer staple: momentum 45, low_volatility 90, risk 20.
- Large pharma with a strong recent uptrend: momentum 92, low_volatility 55, risk 40.

# OUTPUT FORMAT
Return ONLY a single ```toon fenced code block, with no text before or after it.
- One top-level key per TICKER, spelled exactly as provided. A ticker containing a hyphen or a dot (e.g. "BRK-B", "BF.B") MUST be enclosed in double quotes.
- Under each ticker, four fields indented by 2 spaces: `industry` (quoted string), `momentum_score`, `low_volatility_score`, `risk_score` (integers 1-100).
- Every ticker in the input MUST appear, and all four fields MUST be present for each.
- Avoid clustering on multiples of 5: use the full integer range so the ranking stays separable.

EXAMPLE
```toon
NVDA:
  industry: "Semiconductors"
  momentum_score: 94
  low_volatility_score: 26
  risk_score: 63
"BRK-B":
  industry: "Insurance—Diversified"
  momentum_score: 58
  low_volatility_score: 87
  risk_score: 18
```
"""
