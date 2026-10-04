"""
Per-fund quarterly Holding-Based Return (HBR) against the S&P 500.

HBR weights the positions a fund held at the start of a quarter by their value
and takes each one's price return over the quarter, so it measures what the
reported book earned rather than how capital flowed in or out. It is an
estimate built from 13F snapshots: price-only (no dividends), long US equity
only, and blind to anything traded inside the quarter.

The series is computed offline into ``database/fund_performance.csv`` and read
as-is by the static site, like ``performance.csv``.
"""

import csv
import math
from collections.abc import Callable, Iterable
from datetime import date, datetime
from pathlib import Path
from typing import Protocol

import pandas as pd

from app.utils.logger import get_logger, log_safe
from app.utils.strings import get_previous_quarter, get_quarter_date

logger = get_logger(__name__)

EVAL_TOP_N_POSITIONS = 100

# A consensus price needs this many funds reporting the security: the median of
# two filings is their mean, so one bad row would set it.
MIN_REPORTERS = 3

CSV_FIELDS = [
    "fund",
    "quarter",
    "fund_return",
    "benchmark_return",
    "fund_cum_return",
    "benchmark_cum_return",
    "unpriced_weight",
]

HoldingsFn = Callable[[str, str], pd.DataFrame]
FactorsFn = Callable[[str, str], dict[str, float]]
MarketReturnFn = Callable[[str, date, date], float | None]
BenchmarkReturnFn = Callable[[date, date], float | None]
UniversePricesFn = Callable[[str], dict[str, float]]


def quarter_end(quarter: str) -> date:
    """
    The calendar date a 'YYYYQN' quarter ends on.
    """
    return datetime.strptime(get_quarter_date(quarter), "%Y-%m-%d").date()


def _consensus(own: float | None, median: float | None) -> float | None:
    """
    A fund's reported price, else (an exit) what the other tracked funds
    reported. A wrong filed price is never corrected here: the filing register
    restates it in the loaders (app.database.filing_anomalies).
    """
    if own and own > 0:
        return own
    return median if median and median > 0 else None


def _nearest_basis(growth: float, factor: float) -> float:
    """
    Puts a price ratio back on one share basis across a split: of the ratio as
    is, times the factor and divided by it, the one closest to no change. A
    split factor (2, 10, 25...) dwarfs any genuine quarterly move, so the
    choice is unambiguous whether a filing or a cached price was already restated.
    """
    if factor == 1.0 or growth <= 0:
        return growth
    return min((growth, growth * factor, growth / factor), key=lambda g: abs(math.log(g)))


def position_returns(
    prev: pd.DataFrame,
    curr: pd.DataFrame,
    split_factors: dict[str, float],
    closed_return_fn: MarketReturnFn,
    *,
    start: date,
    end: date,
    universe_start_prices: dict[str, float] | None = None,
    universe_prices: dict[str, float] | None = None,
    top_n: int = EVAL_TOP_N_POSITIONS,
) -> pd.DataFrame:
    """
    Weight, quarter return and pricing status of each position held at the
    start of a quarter.

    Both ends are the fund's reported price, already restated by the filing
    register. An exit is priced at the median of every tracked fund's filing
    (``universe_start_prices`` / ``universe_prices``), else from the market via
    ``closed_return_fn``; a position priced by neither counts as flat with
    ``Priced`` False. Split factors are applied to whichever basis the prices
    turn out to be on. A held position's move is never second-guessed here,
    however large: a filed error is corrected upstream by the filing register.
    """
    columns = ["CUSIP", "Ticker", "Company", "Weight", "Return", "Priced"]
    held = prev[prev["Value"] > 0].sort_values("Value", ascending=False).head(top_n)
    total = float(held["Value"].sum())
    if held.empty or total <= 0:
        return pd.DataFrame(columns=columns)

    own_end = curr[curr["Shares"] > 0].groupby("CUSIP")["Reported_Price"].first().to_dict()
    start_medians = universe_start_prices or {}
    end_medians = universe_prices or {}
    returns: list[float] = []
    priced: list[bool] = []
    for cusip, ticker, reported_start in zip(
        held["CUSIP"], held["Ticker"], held["Reported_Price"], strict=True
    ):
        key = str(cusip)
        factor = split_factors.get(key, 1.0)
        start_price = _consensus(float(reported_start), start_medians.get(key))
        own = own_end.get(cusip)
        end_price = _consensus(float(own) if own else None, end_medians.get(key))
        if start_price and end_price:
            returns.append(_nearest_basis(end_price / start_price, factor) - 1)
            priced.append(True)
            continue
        market = closed_return_fn(str(ticker), start, end) if ticker else None
        if market is None:
            returns.append(0.0)
            priced.append(False)
        else:
            returns.append(_nearest_basis(1 + market, factor) - 1)
            priced.append(True)

    frame = held[["CUSIP", "Ticker", "Company"]].copy()
    frame["Weight"] = held["Value"] / total
    frame["Return"] = returns
    frame["Priced"] = priced
    return frame.reset_index(drop=True)


def unpriced_weight(frame: pd.DataFrame) -> float:
    """
    Share of the start book whose quarter return could not be priced.
    """
    if frame.empty:
        return 0.0
    return float(frame.loc[~frame["Priced"].astype(bool), "Weight"].sum())


def reported_prices(frames: Iterable[pd.DataFrame]) -> dict[str, float]:
    """
    Quarter-end price of each CUSIP as the median of what every fund reported,
    so one fund's odd filing does not set the price.
    """
    priced = [f.loc[f["Shares"] > 0, ["CUSIP", "Reported_Price"]] for f in frames if not f.empty]
    if not priced:
        return {}
    grouped = pd.concat(priced).groupby("CUSIP")["Reported_Price"]
    stats = pd.DataFrame({"median": grouped.median(), "count": grouped.size()})
    trusted = stats[stats["count"] >= MIN_REPORTERS]
    return {str(cusip): float(price) for cusip, price in trusted["median"].items()}


def holding_based_return(frame: pd.DataFrame) -> float | None:
    """
    The value-weighted return of a ``position_returns`` frame; None when empty.
    """
    if frame.empty:
        return None
    return float((frame["Weight"] * frame["Return"]).sum())


def _compound(cumulative: float | None, period: float | None) -> float | None:
    """
    Chains one period's return onto a running cumulative return.
    """
    if cumulative is None or period is None:
        return None
    return (1 + cumulative) * (1 + period) - 1


def build_fund_performance(
    funds: Iterable[str],
    quarters: Iterable[str],
    *,
    holdings_fn: HoldingsFn,
    factors_fn: FactorsFn,
    closed_return_fn: MarketReturnFn,
    benchmark_return_fn: BenchmarkReturnFn,
    universe_prices_fn: UniversePricesFn | None = None,
) -> list[dict[str, object]]:
    """
    One row per fund and quarter for which the fund filed both that quarter and
    the one before, with quarterly and cumulative returns for the fund and the
    benchmark over the same windows.
    """
    ordered = sorted(set(quarters))
    benchmark: dict[str, float] = {}
    universe: dict[str, dict[str, float]] = {}
    rows: list[dict[str, object]] = []
    for fund in funds:
        fund_cum: float | None = 0.0
        bench_cum: float | None = 0.0
        for quarter in ordered:
            prev_quarter = get_previous_quarter(quarter)
            if prev_quarter not in ordered:
                continue
            prev = holdings_fn(fund, prev_quarter)
            curr = holdings_fn(fund, quarter)
            if prev.empty or curr.empty:
                continue
            start, end = quarter_end(prev_quarter), quarter_end(quarter)
            if universe_prices_fn is not None:
                for q in (prev_quarter, quarter):
                    if q not in universe:
                        universe[q] = universe_prices_fn(q)
            frame = position_returns(
                prev,
                curr,
                factors_fn(prev_quarter, quarter),
                closed_return_fn,
                start=start,
                end=end,
                universe_start_prices=universe.get(prev_quarter),
                universe_prices=universe.get(quarter),
            )
            fund_return = holding_based_return(frame)
            if fund_return is None:
                continue
            if quarter not in benchmark:
                bench = benchmark_return_fn(start, end)
                if bench is None:
                    raise ValueError(f"No S&P 500 return for {quarter}; refusing to publish")
                benchmark[quarter] = bench
            bench_return = benchmark[quarter]
            fund_cum = _compound(fund_cum, fund_return)
            bench_cum = _compound(bench_cum, bench_return)
            rows.append(
                {
                    "fund": fund,
                    "quarter": quarter,
                    "fund_return": fund_return,
                    "benchmark_return": bench_return,
                    "fund_cum_return": fund_cum,
                    "benchmark_cum_return": bench_cum,
                    "unpriced_weight": unpriced_weight(frame),
                }
            )
    return rows


def _cell(value: object) -> object:
    """
    Rounds floats to six decimals; None becomes an empty cell.
    """
    if value is None:
        return ""
    if isinstance(value, float):
        return round(value, 6)
    return value


def write_fund_performance(rows: list[dict[str, object]], path: Path | str) -> None:
    """
    Writes the series atomically so a failed run never leaves a half file.
    """
    target = Path(path)
    tmp_path = target.with_suffix(".csv.tmp")
    try:
        with tmp_path.open("w", newline="\n", encoding="utf-8") as handle:
            writer = csv.DictWriter(handle, fieldnames=CSV_FIELDS, quoting=csv.QUOTE_ALL)
            writer.writeheader()
            for row in rows:
                writer.writerow({field: _cell(row.get(field)) for field in CSV_FIELDS})
        tmp_path.replace(target)
    except BaseException:
        tmp_path.unlink(missing_ok=True)
        raise


class PriceSource(Protocol):
    """
    The slice of the backtest's PriceCache the market fallback needs.
    """

    def get(self, ticker: str, day: date) -> float | None:
        """
        Price on a day, or None.
        """
        ...

    def last_in_range(self, ticker: str, start: date, end: date) -> float | None:
        """
        Last traded price in (start, end], or None.
        """
        ...


def cached_market_return(cache: PriceSource | None = None) -> MarketReturnFn:
    """
    Market return between two dates from the backtest's persistent price cache.
    A name that stopped trading inside the window (takeover, delisting) is
    valued at its last trade rather than counted flat; None when no start
    price or no trade at all is known.
    """
    if cache is None:
        from app.backtest.price_cache import PriceCache

        cache = PriceCache()
    source = cache

    def market_return(ticker: str, start: date, end: date) -> float | None:
        """
        Exit (or last-trade) price over start price, minus one.
        """
        first = source.get(ticker, start)
        last = source.get(ticker, end) or source.last_in_range(ticker, start, end)
        if first is None or last is None:
            logger.warning("No market prices for %s, left unpriced", log_safe(ticker))
            return None
        return last / first - 1

    return market_return


def registry_split_factors() -> FactorsFn:
    """
    Split factors between two quarters from the committed split registry.
    """
    from app.analysis.splits import factors_between
    from app.database.splits import load_split_factors

    registry = load_split_factors()
    return lambda prev, curr: factors_between(registry, prev, curr)


def tracked_universe_prices(holdings_fn: HoldingsFn) -> UniversePricesFn:
    """
    Quarter-end prices reported across every tracked fund, computed once per quarter.
    """
    from app.database.quarters import load_hedge_funds

    funds = [str(fund["Fund"]) for fund in load_hedge_funds()]
    memo: dict[str, dict[str, float]] = {}

    def prices(quarter: str) -> dict[str, float]:
        """
        CUSIP -> median reported price for the quarter.
        """
        if quarter not in memo:
            memo[quarter] = reported_prices(holdings_fn(f, quarter) for f in funds)
        return memo[quarter]

    return prices


def rebuild_fund_performance(path: Path | str | None = None) -> str:
    """
    Computes every tracked fund's series with the cached price chain and writes
    ``database/fund_performance.csv``. Returns the written path.
    """
    import app.database as _db
    from app.database import FUND_PERFORMANCE_FILE, get_all_quarters, load_fund_holdings
    from app.database.quarters import load_hedge_funds

    loaded: dict[tuple[str, str], pd.DataFrame] = {}

    def holdings_for(fund: str, quarter: str) -> pd.DataFrame:
        """
        Loads a fund's quarter once; the universe prices reuse every load.
        """
        key = (fund, quarter)
        if key not in loaded:
            loaded[key] = load_fund_holdings(fund, quarter)
        return loaded[key]

    market_return = cached_market_return()
    rows = build_fund_performance(
        [str(fund["Fund"]) for fund in load_hedge_funds()],
        get_all_quarters(),
        holdings_fn=holdings_for,
        factors_fn=registry_split_factors(),
        closed_return_fn=market_return,
        benchmark_return_fn=lambda start, end: market_return("SPY", start, end),
        universe_prices_fn=tracked_universe_prices(holdings_for),
    )
    target = Path(path) if path is not None else _db._safe_db_join(FUND_PERFORMANCE_FILE)
    write_fund_performance(rows, target)
    logger.success("Wrote %d fund performance row(s) to %s", len(rows), target)
    return str(target)
