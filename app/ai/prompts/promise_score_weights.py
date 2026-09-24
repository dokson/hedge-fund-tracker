from app.ai.promise_score_validator import PromiseScoreValidator


def promise_score_weights_prompt(quarter: str) -> str:
    """
    Build prompt for getting Promise Score weights.
    """
    return f"""
# ROLE
You are a quantitative portfolio manager specializing in 13F analysis and institutional flow-based strategies. You favour signals that survive a cross-sectional rank transform over signals that depend on raw magnitude.

# TASK
Choose the weights of a "Promise Score" that ranks stocks by institutional conviction and accumulation for Quarter {quarter}. All data comes from the public 13F filings of top global hedge funds.

# CONSTRAINTS (all are enforced by code; a violation is rejected and the request is retried)
- Use between 6 and 10 metrics. Omit any metric you would weight 0.
- `Seller_Count` and `Close_Count`, if included, MUST carry a negative weight.
- EVERY other metric MUST carry a strictly positive weight.
- Metric names MUST come verbatim from AVAILABLE METRICS, each used at most once.
- Every weight MUST be a finite, non-zero number.
- Weights express RELATIVE IMPORTANCE: their magnitudes only matter relative to each other, because the code normalizes them. Any scale works (e.g. 0.4 and 0.2, or 4 and 2).

# HOW YOUR WEIGHTS ARE USED
Each metric is first converted to a CROSS-SECTIONAL PERCENTILE RANK (0-1) over the whole stock universe; the Promise Score combines those ranks with your weights, normalized by the code. Two consequences follow:
- Magnitude is discarded. A metric's outliers carry no more influence than its median, so do not weight a metric up because its raw scale is large.
- Correlated metrics double-count. `Buyer_Count`, `Seller_Count`, `Holder_Count`, `Net_Buyers` and `Buyer_Seller_Ratio` move together, so spreading weight across them concentrates the model on breadth instead of diversifying it.
Multiplying every weight by the same positive constant leaves the ranking unchanged.

# AVAILABLE METRICS
```toon
Total_Value: "Aggregate dollar value held by all institutions (overall institutional ownership/popularity)."
Total_Delta_Value: "Net change in dollar holdings by all institutions (raw capital allocation)."
Max_Portfolio_Pct: "Highest single-fund percentage allocation to the stock (individual conviction)."
Buyer_Count: "Number of institutions increasing positions (breadth of buying)."
Seller_Count: "Number of institutions reducing positions (selling activity)."
Close_Count: "Number of institutions fully exiting their positions (strong negative signal)."
Holder_Count: "Total number of institutions currently holding the stock (popularity/consensus)."
New_Holder_Count: "Number of institutions initiating new positions (emerging interest). Skewed by IPO cycles."
High_Conviction_Count: "Number of top-tier funds opening large (>3%) or Top 10 positions. Strongest conviction signal."
Ownership_Delta_Avg: "Average percentage increase in shares for existing holders (velocity of accumulation)."
Portfolio_Concentration_Avg: "Average concentration (Top 10 holdings / AUM) of the funds holding this stock (pure-plays vs diversified managers)."
Net_Buyers: "Buyer_Count minus Seller_Count (net institutional sentiment)."
Delta: "Percentage change in total value held. Unstable for stocks with a small prior base; prefer Total_Delta_Value for capital flow."
Buyer_Seller_Ratio: "Buyer_Count / Seller_Count. Extreme when Seller_Count is near zero, which is typical of recent IPOs. Secondary to raw high-conviction counts."
```

# WEIGHTING PHILOSOPHY
- Prioritize high conviction: `High_Conviction_Count` and `Max_Portfolio_Pct` are the strongest evidence of serious research and commitment.
- Velocity of accumulation: `Ownership_Delta_Avg` shows how aggressively existing holders are doubling down.
- Quality over breadth: favour `High_Conviction_Count` over plain `Buyer_Count` when identifying elite opportunities.
- Concentration context: a high `Portfolio_Concentration_Avg` is informative only alongside buying, so treat it as a tiebreaker rather than a primary driver.

# OUTPUT FORMAT
Return a JSON object with a single field `weights`: a list of 6 to 10 items, one per chosen metric, each with `metric` (the metric name) and `weight` (a number).
"""


# Strict mode needs every property required, so the chosen subset of metrics
# is a list of {metric, weight} items instead of an object keyed by metric.
WEIGHTS_SCHEMA: dict = {
    "type": "object",
    "properties": {
        "weights": {
            "type": "array",
            "minItems": PromiseScoreValidator.MIN_METRICS,
            "maxItems": PromiseScoreValidator.MAX_METRICS,
            "items": {
                "type": "object",
                "properties": {
                    "metric": {"type": "string", "enum": PromiseScoreValidator.AVAILABLE_METRICS},
                    "weight": {"type": "number"},
                },
                "required": ["metric", "weight"],
                "additionalProperties": False,
            },
        }
    },
    "required": ["weights"],
    "additionalProperties": False,
}
