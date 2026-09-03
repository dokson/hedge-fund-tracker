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
- The weights MUST sum to 1.0 (tolerance +/-0.05).

# HOW YOUR WEIGHTS ARE USED
Each metric is first converted to a CROSS-SECTIONAL PERCENTILE RANK (0-1) over the whole stock universe; the Promise Score is the weighted sum of those ranks. Two consequences MUST shape your choice:
- Magnitude is discarded. A metric's outliers carry no more influence than its median, so do not weight a metric up because its raw scale is large.
- Correlated metrics double-count. `Buyer_Count`, `Seller_Count`, `Holder_Count`, `Net_Buyers` and `Buyer_Seller_Ratio` move together, so spreading weight across them concentrates the model on breadth instead of diversifying it.
The ranking is invariant to rescaling every weight by a positive constant: the sum constraint exists for comparability across runs, not for correctness.

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
Return ONLY a single ```toon fenced code block, with no text before or after it. Inside the block: a flat object, one `Metric_Name: <float>` line per metric, no nesting, no comments.

EXAMPLE
```toon
High_Conviction_Count: 0.30
Max_Portfolio_Pct: 0.20
Ownership_Delta_Avg: 0.15
Net_Buyers: 0.15
Total_Delta_Value: 0.15
New_Holder_Count: 0.05
Close_Count: -0.07
Seller_Count: -0.03
```
"""
