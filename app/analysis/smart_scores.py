"""
Composite 1-10 "smart score" per stock, built purely from institutional signals.

Each component is a percentile rank (0-100) across the stocks held in the
current quarter's merged view (13F plus recent 13D/G + Form 4 — so fresh
non-quarterly accumulation lifts the score through the components themselves):

- Breadth: how many tracked funds hold the stock (Holder_Count)
- Momentum: net institutional buying pressure (Net_Buyers)
- Conviction: average portfolio allocation across holders (Avg_Portfolio_Pct),
  plus a capped bonus per high-conviction new entry (a position opened straight
  into a portfolio's top ranks). The signal is too sparse to be its own
  percentile — as a mean component it would *penalize* strong stocks that have
  it — so it strengthens Conviction instead, where it semantically belongs.

The composite is the mean of the three components rescaled to [1, 10].
Registry tickers with no institutional presence get the explicit floor (1.0)
instead of a missing row, without diluting the held universe's percentiles.
Deliberately no sell-side analyst inputs — the edge is what funds actually do
— and the core is reconstructable point-in-time, so the same formula is
backtestable. Descriptive, not a forecast.
"""

import pandas as pd

SCORE_COLUMNS = [
    "Ticker",
    "Smart_Score",
    "Breadth_Score",
    "Momentum_Score",
    "Conviction_Score",
]

_COMPONENT_COLUMNS = SCORE_COLUMNS[2:5]

# Percentile points added to Conviction per high-conviction new entry, before
# the 0-100 cap. A-priori choice, NOT tuned on backtest returns.
HC_ENTRY_CONVICTION_BONUS = 10.0


def _components(stock_df: pd.DataFrame) -> dict[str, pd.Series]:
    """
    The three component percentile series, keyed by their output column name —
    the single place the component definitions live.
    """
    return {
        "Breadth_Score": _percentile(stock_df["Holder_Count"]),
        "Momentum_Score": _percentile(stock_df["Net_Buyers"]),
        "Conviction_Score": _conviction_score(stock_df),
    }


def _composite(components: dict[str, pd.Series]) -> pd.Series:
    """
    Mean of the available components rescaled to the 1-10 band.
    """
    stacked = pd.concat(components.values(), axis=1)
    return 1 + 9 * stacked.mean(axis=1, skipna=True) / 100


def score_core(stock_df: pd.DataFrame) -> pd.Series:
    """
    The 1-10 composite from the institutional percentiles — the point-in-time
    reconstructable core shared by the published scores and the backtest screen.
    """
    return _composite(_components(stock_df))


def _conviction_score(stock_df: pd.DataFrame) -> pd.Series:
    """
    Conviction percentile plus the capped high-conviction-entry bonus.
    """
    conviction = _percentile(stock_df["Avg_Portfolio_Pct"])
    if "High_Conviction_Count" in stock_df.columns:
        conviction = conviction + stock_df["High_Conviction_Count"] * HC_ENTRY_CONVICTION_BONUS
    return conviction.clip(upper=100.0)


def compute_smart_scores(
    stock_df: pd.DataFrame,
    registry_tickers: list[str] | None = None,
) -> pd.DataFrame:
    """
    Computes component percentiles and the 1-10 composite for every held
    ticker, then floors the rest of the registry (when provided) at 1.0.
    """
    if stock_df.empty:
        return pd.DataFrame(columns=SCORE_COLUMNS)

    components = _components(stock_df)
    scores = stock_df[["Ticker"]].copy()
    for column, series in components.items():
        scores[column] = series
    scores["Smart_Score"] = _composite(components).round(1)
    scores[_COMPONENT_COLUMNS] = scores[_COMPONENT_COLUMNS].round(1)
    scores = scores[SCORE_COLUMNS]

    if registry_tickers:
        held = set(scores["Ticker"])
        missing = sorted({t for t in registry_tickers if t and t not in held})
        if missing:
            floor = pd.DataFrame(
                {
                    "Ticker": missing,
                    "Smart_Score": 1.0,
                    "Breadth_Score": 0.0,
                    "Momentum_Score": 0.0,
                    "Conviction_Score": 0.0,
                }
            )
            scores = pd.concat([scores, floor], ignore_index=True)

    return scores


def _percentile(series: pd.Series) -> pd.Series:
    """
    Percentile rank (0-100) preserving NaN for missing observations.
    """
    return series.rank(pct=True) * 100
