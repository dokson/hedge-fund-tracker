"""
Filing-implied prices: a quarter's 13F market value per share, used as the
entry price of last resort when no provider still serves a name's history
(providers drop delisted tickers). The quarter is the one the screen is built
from, so the price was public by the entry date.
"""

from collections.abc import Callable
from functools import cache

import pandas as pd

from app.database import load_quarterly_data, load_stocks
from app.stocks.utils.identifiers import is_equity_cusip
from app.utils.pd import get_numeric_series


def implied_prices(quarter_rows: pd.DataFrame, stocks: pd.DataFrame) -> dict[str, float]:
    """
    Map each ticker to total equity value over total shares across its quarter rows.

    CUSIPs resolve to tickers through stocks.csv, as in the stock-level
    aggregation; debt rows, zero-share rows and unknown CUSIPs are skipped.
    """
    rows = quarter_rows[quarter_rows["CUSIP"].map(is_equity_cusip)]
    frame = pd.DataFrame(
        {
            "Ticker": rows["CUSIP"].map(stocks["Ticker"]),
            "Shares": pd.to_numeric(rows["Shares"], errors="coerce"),
            "Value": get_numeric_series(rows["Value"]),
        }
    ).dropna()
    frame = frame[frame["Shares"] > 0]
    totals = frame.groupby("Ticker")[["Value", "Shares"]].sum()
    return {str(t): float(v / s) for t, v, s in totals.itertuples() if v > 0}


@cache
def filing_implied_prices(quarter: str) -> dict[str, float]:
    """
    Filing-implied prices for every equity ticker held in a quarter's 13F filings.
    """
    return implied_prices(load_quarterly_data(quarter), load_stocks())


def latest_filing_price(
    ticker: str,
    quarter: str,
    quarters: list[str],
    prices_fn: Callable[[str], dict[str, float]] = filing_implied_prices,
) -> float | None:
    """
    The filing-implied price from `quarter` or, when the name was no longer held
    there (a closed position files zero shares), from the latest earlier quarter.
    Never looks at a quarter after `quarter`, so the price was public by entry.
    """
    for candidate in sorted((q for q in quarters if q <= quarter), reverse=True):
        price = prices_fn(candidate).get(ticker)
        if price is not None:
            return price
    return None
