def promise_score_weights_prompt(quarter: str) -> str:
    """
    Build prompt for getting Promise Score weights.
    """
    return f"""
ROLE: You are a quantitative portfolio manager specializing in 13F analysis and institutional flow strategies.

CONTEXT: Quarter {quarter} - Analyzing institutional fund movements to identify emerging opportunities.

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
- `Seller_Count` and `Close_Count` must have a negative weight if included.
- Do not include any metric with a weight of 0.

OUTPUT REQUIREMENTS:
Return ONLY a valid JSON object with metric names as keys and weights as values.
Weights must be decimal numbers that sum to 1.0.

EXAMPLE FORMATS:
{{"Total_Delta_Value": 0.4, "New_Holder_Count": 0.35, "Max_Portfolio_Pct": 0.25}}

OR

{{"New_Holder_Count": 0.3, "Net_Buyers": 0.25, "Close_Count": -0.2, "Max_Portfolio_Pct": 0.15, "Buyer_Count": 0.1}}

OUTPUT (JSON only):
"""
