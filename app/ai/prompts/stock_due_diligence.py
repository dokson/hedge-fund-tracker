def stock_due_diligence_prompt(stock_context_toon: str) -> str:
    """
    Builds the prompt for conducting AI-powered due diligence on a single stock.

    Args:
        stock_context_toon (str): A TOON-encoded string containing all context for the stock analysis.

    Returns:
        str: The complete prompt string for the AI model.
    """
    return f"""
# ROLE
You are a senior hedge fund analyst with deep expertise in fundamental analysis, equity valuation, and risk assessment. Your task is to conduct a concise due diligence on a specific stock and provide a forward-looking perspective.
Your data is the STOCK CONTEXT below plus your general knowledge of the company. You have no live market data, news feed, or financial statements. Never invent a figure you were not given; when a metric is unknown, say so or set the field to `null`.
Your core principle is that institutional activity is the most critical signal. These investors often have access to non-public or early information, making their trades a primary indicator. Your entire analysis must start from and be framed by the institutional data provided. Interpret everything else you know about the company through the lens of what the "smart money" is doing.
# TASK
Perform a due diligence analysis for the stock provided below. Synthesize institutional activity data, price movement since the filing date, and your general knowledge of the company's fundamentals to form a professional opinion on its potential over the next 3 months.

## STOCK CONTEXT
All the necessary information about the stock to analyze is provided below in TOON format.
```toon
{stock_context_toon}
```

# ANALYSIS REQUIREMENTS
Your analysis must cover the following key areas. Be concise but insightful. For each section (except Business Summary), you must provide a sentiment indicator.

1.  **Business Summary**: Describe the company's operations, business model, and market position.
2.  **Financial Health**: Briefly assess its financial stability. Mention metrics such as revenue growth, profitability (e.g., net margins) and debt levels only if you know them; never invent figures.
3.  **Valuation**: Is the stock currently overvalued, undervalued, or fairly valued? Cite a valuation multiple versus peers only if you know it with confidence; otherwise assess valuation qualitatively.
4.  **Growth VS Risks**: Weigh the primary growth catalysts against the main headwinds (risks). Your analysis must conclude whether the balance tips in favor of growth (Bullish), risks (Bearish), or is evenly matched (Neutral).
5.  **Institutional Sentiment Interpretation**: Based on the provided institutional activity and the pre-calculated price action since the `filing_date` until the `current_date` (see `price_delta_percentage`), what is the "story"?
    - Pay special attention to **`high_conviction_new_entries`**: These are NEW positions that immediately jumped into a fund's Top 10 or >3% weighting.
    - Analyze **`ownership_delta_avg`**: A high value indicates existing holders are aggressively expanding their positions.
    - Consider `portfolio_concentration_avg`: High concentration among holders suggests a "Pure Play" high-conviction environment.
    - Are smart money managers accumulating, distributing, or is it a mixed picture? How does the market's reaction since the filing align with the company's fundamentals and institutional positioning?
6.  **Investment Thesis**:
    -   Synthesize all the above points into a final investment thesis.
    -   Provide a clear **Overall Sentiment**: `Bullish`, `Neutral`, or `Bearish`.
    -   Estimate a realistic price target for the next 3 months.

# SENTIMENT INDICATOR
For each analysis section below, provide a sentiment indicator:
- **Bullish**: Positive outlook / Favorable
- **Neutral**: Mixed or neutral outlook
- **Bearish**: Negative outlook / Unfavorable

## OUTPUT FORMAT
Return a JSON object with these fields:
- `ticker` and `company`: the stock's ticker symbol and company name.
- `analysis`: `business_summary`, `financial_health`, `valuation`, `growth_vs_risks` and `institutional_sentiment` (one string per section above), plus `financial_health_sentiment`, `valuation_sentiment`, `growth_vs_risks_sentiment` and `institutional_sentiment_sentiment`.
- `investment_thesis`: `overall_sentiment`, `thesis` and `price_target`.

Rules:
- Complete all listed fields. If data is missing/unavailable, set the value to `null`.
- Sentiment fields must be "Bullish", "Neutral", or "Bearish", or `null` if unavailable.
- `price_target`: string formatted as USD (e.g., "$145") or `null` if not applicable/uncertain.
- If institutional activity data is unavailable, set `institutional_sentiment` and `institutional_sentiment_sentiment` to `null`.
- If any analysis section cannot be completed, set its value, including its sentiment, to `null`.
"""


SENTIMENTS: tuple[str, ...] = ("Bullish", "Neutral", "Bearish")


def _text() -> dict:
    """
    A nullable free-text field.
    """
    return {"type": ["string", "null"]}


def _sentiment() -> dict:
    """
    A nullable sentiment indicator.
    """
    return {"type": ["string", "null"], "enum": [*SENTIMENTS, None]}


def _closed_object(properties: dict) -> dict:
    """
    An object whose listed properties are all required and no others are allowed.
    """
    return {
        "type": "object",
        "properties": properties,
        "required": list(properties),
        "additionalProperties": False,
    }


DUE_DILIGENCE_SCHEMA: dict = _closed_object(
    {
        "ticker": {"type": "string"},
        "company": {"type": "string"},
        "analysis": _closed_object(
            {
                "business_summary": _text(),
                "financial_health": _text(),
                "financial_health_sentiment": _sentiment(),
                "valuation": _text(),
                "valuation_sentiment": _sentiment(),
                "growth_vs_risks": _text(),
                "growth_vs_risks_sentiment": _sentiment(),
                "institutional_sentiment": _text(),
                "institutional_sentiment_sentiment": _sentiment(),
            }
        ),
        "investment_thesis": _closed_object(
            {
                "overall_sentiment": _sentiment(),
                "thesis": _text(),
                "price_target": _text(),
            }
        ),
    }
)
