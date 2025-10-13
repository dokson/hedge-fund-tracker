def promise_score_weights_prompt(quarter: str) -> str:
    """
    Build prompt for getting Promise Score weights.
    """
    return f"""
# ROLE
You are a quantitative portfolio manager specializing in 13F analysis and institutional flow-based strategies.

# CONTEXT
Analyzing institutional fund activity for Quarter {quarter} to uncover emerging equity opportunities. All data is sourced from top global hedge funds' public filings.

# TASK
Develop the optimal weights for a "Promise Score" algorithm designed to identify stocks demonstrating the highest levels of institutional conviction and momentum.

# PROCESS
Begin with a concise checklist (3-7 bullets) of your conceptual weighting approach before calculating the final weights.
After defining the weights, perform an internal validation step:
1.  **Sum Check**: Verify that the sum of all weights is *exactly* 1.0.
2.  **Constraint Check**: Ensure all other constraints (e.g., negative weights for `Seller_Count`) are met.
3.  **Self-Correction**: If the sum is not 1.0, normalize the weights or adjust them until the sum is precisely 1.0 before generating the final JSON output.

# AVAILABLE METRICS
- **Total_Value**: Aggregate dollar value held by all institutions (overall institutional ownership/popularity).
- **Total_Delta_Value**: Net change in dollar holdings by all institutions (indicates raw capital allocation).
- **Max_Portfolio_Pct**: Highest single-fund percentage allocation to the stock (shows individual conviction).
- **Buyer_Count**: Number of institutions increasing positions (captures breadth of buying).
- **Seller_Count**: Number of institutions reducing positions (measures selling activity).
- **Close_Count**: Number of institutions fully exiting their positions (strong negative signal).
- **Holder_Count**: Total number of institutions currently holding the stock (measures popularity/consensus).
- **New_Holder_Count**: Number of institutions initiating new positions (captures emerging interest).
- **Net_Buyers**: Buyer_Count minus Seller_Count (shows net institutional sentiment).

# WEIGHTING PHILOSOPHY
Emphasize input features that are most predictive of future outperformance:
- Prefer signals of high-conviction capital flows.
- Prioritize new institutional accumulation over consensus or existing popularity.
- Favor breadth and scale of buying activity, and penalize strong negative flows.
- Use forward-looking momentum proxies.

**Caution:**
`New_Holder_Count` can be large for recent IPOs or highly active stocks. Although a critical signal, avoid overweighting it to prevent skew towards IPOs.

# CONSTRAINTS
- **CRITICAL**: The sum of all weights *must* be exactly 1.0. This is a non-negotiable rule.
- If included, `Seller_Count` and `Close_Count` must have *negative* weights.
- Do not include any metric with a weight of 0 (omit metrics with zero weights).

# OUTPUT REQUIREMENTS
1.  **JSON Only**: The entire output must be a single, valid JSON object. Do not include any text, explanations, or markdown formatting like ` ```json ` before or after the JSON.
2.  **Valid Structure**: The JSON must be a flat object where keys are metric names (strings) and values are their corresponding weights (numbers).

**IMPORTANT**: Before outputting the JSON, double-check that the sum of all weight values equals exactly 1.00.

# JSON SCHEMA
The output must strictly conform to this structure:
`{{ "METRIC_NAME_1": <weight_1>, "METRIC_NAME_2": <weight_2>, ... }}`
- Keys must be strings from the "AVAILABLE METRICS" list.
- Values must be floating-point numbers.

# OUTPUT FORMAT
A single, raw JSON object. No extra text.

EXAMPLE FORMATS:
{{"Total_Delta_Value": 0.4, "New_Holder_Count": 0.35, "Max_Portfolio_Pct": 0.25}}

OR

{{"New_Holder_Count": 0.5, "Net_Buyers": 0.4, "Close_Count": -0.2, "Max_Portfolio_Pct": 0.2, "Buyer_Count": 0.1}}
"""
