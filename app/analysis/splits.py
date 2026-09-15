"""
Stock-split detection across the tracked 13F universe.

A 13F reports share counts as of quarter end, so a split inflates them without
anyone having traded: quarter over quarter the position reads as a purchase of
several times its own size, and every delta derived from share counts inherits
the error. Forward splits leave the CUSIP unchanged, so nothing else in the
comparison path notices them.

A split is a published fact, so the price provider decides -- the filings only
say which securities are worth asking about. That order matters: the filings
alone cannot tell a 2:1 split from a fund doubling its position, and gating on
them produced one true split for every twenty-one ordinary trades.

The holder-agreement test is the fallback for securities the provider cannot
serve (delisted, foreign, mutual funds). A holder that did nothing across the
split lands on exactly the split factor, so three of them agreeing to within a
fraction of a percent is a coincidence trading cannot manufacture. It needs
three holders, and two thirds of the universe is held by fewer, which is
exactly why it is the fallback and not the source.
"""

import time
from collections.abc import Callable
from datetime import date

import numpy as np
import pandas as pd

from app.database import get_all_quarters, load_quarterly_data
from app.utils.logger import get_logger, log_safe
from app.utils.pd import get_numeric_series
from app.utils.strings import get_previous_quarter, get_quarter_date

logger = get_logger(__name__)

MIN_AGREEING_HOLDERS = 3

# Holders are called agreeing within this relative distance of each other.
_AGREEMENT_TOLERANCE = 0.01

# Share ratios inside this band are ordinary trading; no split is this small.
_DEADBAND = (0.72, 1.38)

# The security's price move once the candidate factor is removed. A split
# leaves this near 1; a position that genuinely grew leaves it near the share
# ratio itself, far outside the band.
_TRUE_MOVE_BAND = (0.70, 1.50)

# A split factor is a ratio of small whole numbers. Bounding the numerator as
# well as the denominator is what keeps 249/50 from passing as "simple".
_MAX_SNAP_NUMERATOR = 50
_MAX_SNAP_DENOMINATOR = 10

# Worth a provider lookup: wide on purpose, since the provider adjudicates and
# this only keeps the number of lookups down.
_CANDIDATE_TRUE_MOVE_BAND = (0.6, 1.7)

# How far the filed share basis may sit from the factor the provider reports.
# Holders that also traded across the split pull the median off it, so this is
# loose; what it has to catch is the factor no holder's share count followed.
_CONFIRMATION_BAND = (0.8, 1.25)

# Seconds between provider lookups. Yahoo throttles bulk sweeps and answers a
# throttled sweep with empty data rather than an error.
PROVIDER_PACING_SECONDS = 1.2

_REQUIRED_COLUMNS = ("CUSIP", "Shares", "Value", "Shares_previous", "Value_previous")

# Ex-dates and factors for a ticker, or None when the lookup itself failed.
SplitProvider = Callable[[str], list[tuple[date, float]] | None]


def _snap_to_simple_ratio(factor: float) -> float:
    """
    Rounds a factor to the nearest simple rational, preferring the smallest
    denominator and leaving it unchanged when none is close. Filed share counts
    are rounded, so holders agree to a few parts in a thousand rather than
    exactly; without this an untouched position would keep a residual delta
    after rescaling.
    """
    tolerance = float(np.log(1 + _AGREEMENT_TOLERANCE))
    for denominator in range(1, _MAX_SNAP_DENOMINATOR + 1):
        numerator = round(factor * denominator)
        if not 1 <= numerator <= _MAX_SNAP_NUMERATOR:
            continue
        candidate = numerator / denominator
        if abs(float(np.log(candidate / factor))) <= tolerance:
            return candidate
    return factor


def _largest_agreeing_cluster(ratios: np.ndarray) -> np.ndarray:
    """
    Returns the largest group of share ratios lying within the agreement
    tolerance of one of its own members.
    """
    log_ratios = np.log(ratios)
    tolerance = np.log(1 + _AGREEMENT_TOLERANCE)
    memberships = [np.abs(log_ratios - centre) <= tolerance for centre in log_ratios]
    return ratios[max(memberships, key=np.count_nonzero)]


def _split_factor(holdings: pd.DataFrame) -> float | None:
    """
    The split factor for one security across a quarter transition, or None when
    the holders' share ratios do not agree or the price does not confirm them.
    """
    candidates = holdings[(holdings["ratio"] <= _DEADBAND[0]) | (holdings["ratio"] >= _DEADBAND[1])]
    if len(candidates) < MIN_AGREEING_HOLDERS:
        return None

    cluster = _largest_agreeing_cluster(candidates["ratio"].to_numpy())
    if len(cluster) < MIN_AGREEING_HOLDERS:
        return None

    factor = _snap_to_simple_ratio(float(np.exp(np.log(cluster).mean())))
    price_ratio = float(np.median(holdings["price"] / holdings["price_previous"]))
    true_move = price_ratio * factor
    if not _TRUE_MOVE_BAND[0] < true_move < _TRUE_MOVE_BAND[1]:
        return None

    return factor


def _prepare(positions: pd.DataFrame) -> pd.DataFrame:
    """
    Keeps the positions held in both quarters and adds the share ratio and the
    two quarter-end prices every measure here is built from.
    """
    if positions.empty or not set(_REQUIRED_COLUMNS) <= set(positions.columns):
        return pd.DataFrame()

    held = positions.assign(
        **{
            column: pd.to_numeric(positions[column], errors="coerce")
            for column in _REQUIRED_COLUMNS[1:]
        }
    )
    held = held[
        (held["Shares"] > 0)
        & (held["Shares_previous"] > 0)
        & (held["Value"] > 0)
        & (held["Value_previous"] > 0)
    ]
    if held.empty:
        return pd.DataFrame()

    return held.assign(
        ratio=held["Shares"] / held["Shares_previous"],
        price=held["Value"] / held["Shares"],
        price_previous=held["Value_previous"] / held["Shares_previous"],
    )


def _is_candidate(holdings: pd.DataFrame) -> bool:
    """
    True when some holder's share count moved far enough, against a price that
    moved the opposite way, for a split to be worth ruling out.
    """
    moved = holdings[(holdings["ratio"] <= _DEADBAND[0]) | (holdings["ratio"] >= _DEADBAND[1])]
    if moved.empty:
        return False

    price_ratio = float(np.median(holdings["price"] / holdings["price_previous"]))
    true_moves = price_ratio * moved["ratio"]
    low, high = _CANDIDATE_TRUE_MOVE_BAND
    return bool(((true_moves > low) & (true_moves < high)).any())


def _is_confirmed(holdings: pd.DataFrame, factor: float) -> bool:
    """
    True when the filed share counts really moved by the factor the provider
    reports.

    The provider's split series also carries events that restate the price
    without restating share counts -- a spinoff's basis adjustment, a small
    stock dividend. Applying one of those to share counts would manufacture the
    very error this module removes, turning untouched positions into large
    sales, so the filings get the last word.
    """
    if _DEADBAND[0] < factor < _DEADBAND[1]:
        return False
    agreement = float(np.median(holdings["ratio"])) / factor
    return _CONFIRMATION_BAND[0] <= agreement <= _CONFIRMATION_BAND[1]


def _quarter_window(quarter: str) -> tuple[date, date]:
    """
    First and last calendar day of a 'YYYYQN' quarter.
    """
    end = date.fromisoformat(get_quarter_date(quarter))
    return date(end.year, end.month - 2, 1), end


def detect_splits(positions: pd.DataFrame) -> dict[str, float]:
    """
    Maps CUSIP to split factor for every security split over one quarter
    transition, given the universe's positions in both quarters.

    Expects one row per (fund, security) carrying Shares/Value and their
    _previous counterparts; securities entered or exited during the quarter are
    ignored, having no ratio to agree on.
    """
    held = _prepare(positions)
    if held.empty:
        return {}

    factors = {}
    for cusip, holdings in held.groupby("CUSIP"):
        factor = _split_factor(holdings)
        if factor is None:
            continue
        factors[str(cusip)] = factor
        ratio = f"{factor:g}:1" if factor >= 1 else f"1:{1 / factor:g}"
        logger.info(
            "Detected %s split on %s across %s holders",
            log_safe(ratio),
            log_safe(str(cusip)),
            len(holdings),
            emoji="🔀",
        )

    return factors


def splits_for_transition(
    positions: pd.DataFrame, quarter: str, provider: SplitProvider
) -> list[dict[str, object]]:
    """
    Registry rows for the splits that took effect in ``quarter``, given the
    universe's positions in that quarter and the one it is compared against.

    Only securities whose filed share counts moved are looked up, and the
    provider's answer is final: it reporting no split for a quarter is what
    keeps a fund that doubled its position from being erased as a split. The
    holder-agreement fallback applies only when the lookup itself failed.
    """
    held = _prepare(positions)
    if held.empty:
        return []

    start, end = _quarter_window(quarter)
    rows: list[dict[str, object]] = []
    for cusip, holdings in held.groupby("CUSIP"):
        if not _is_candidate(holdings):
            continue

        tickers = holdings["Ticker"].dropna() if "Ticker" in holdings else pd.Series(dtype=str)
        ticker = str(tickers.iloc[0]) if len(tickers) else ""
        reported = provider(ticker) if ticker else None

        if reported is not None:
            within = [(day, factor) for day, factor in reported if start <= day <= end]
            if not within:
                continue
            factor = float(np.prod([factor for _, factor in within]))
            if not _is_confirmed(holdings, factor):
                continue
            effective = max(day for day, _ in within).isoformat()
            source = "yfinance"
        else:
            agreed = _split_factor(holdings)
            if agreed is None:
                continue
            factor, effective, source = agreed, "", "agreement"

        ratio = f"{factor:g}:1" if factor >= 1 else f"1:{1 / factor:g}"
        logger.info(
            "%s split on %s (%s) in %s, via %s",
            log_safe(ratio),
            log_safe(ticker or str(cusip)),
            log_safe(str(cusip)),
            log_safe(quarter),
            log_safe(source),
            emoji="🔀",
        )
        rows.append(
            {
                "Quarter": quarter,
                "Date": effective,
                "CUSIP": str(cusip),
                "Ticker": ticker,
                "Factor": factor,
            }
        )

    return rows


def _paced(provider: SplitProvider, pacing: float) -> SplitProvider:
    """
    Wraps a provider so each ticker is looked up once and lookups are spaced
    out, since a throttled sweep comes back empty rather than failing.
    """
    answers: dict[str, list[tuple[date, float]] | None] = {}

    def lookup(ticker: str) -> list[tuple[date, float]] | None:
        if ticker not in answers:
            if answers:
                time.sleep(pacing)
            answers[ticker] = provider(ticker)
        return answers[ticker]

    return lookup


def _quarter_positions(quarter: str) -> pd.DataFrame:
    """
    One row per (fund, security) for a quarter, with Value parsed to a number.
    """
    holdings = load_quarterly_data(quarter)
    if holdings.empty:
        return holdings
    return holdings.assign(
        Shares=pd.to_numeric(holdings["Shares"], errors="coerce"),
        Value=get_numeric_series(holdings["Value"]),
    )[["Fund", "CUSIP", "Ticker", "Shares", "Value"]]


def scannable_quarters(quarters: list[str] | None = None) -> list[str]:
    """
    The quarters a scan can actually cover, oldest first.

    A quarter is scannable only if the one before it is also on record, since a
    split is visible in the change between two filings. The earliest quarter on
    record therefore never appears.
    """
    known = sorted(get_all_quarters())
    wanted = sorted(set(quarters) & set(known)) if quarters else known
    return [q for q in wanted if get_previous_quarter(q) in known]


def latest_scannable_quarter() -> str | None:
    """
    The most recent quarter a scan can cover, or None when there are too few.
    """
    scannable = scannable_quarters()
    return scannable[-1] if scannable else None


def rebuild_split_registry(
    provider: SplitProvider | None = None, quarters: list[str] | None = None
) -> list[dict[str, object]]:
    """
    Scans quarter transitions and returns one registry row per split, ready for
    app.database.splits.save_split_factors.

    ``quarters`` limits the scan, which is what makes a routine run cheap: only
    the newest quarter needs rescanning, and each lookup is paced against the
    provider's rate limit. Pass the same quarters to ``save_split_factors`` as
    ``replacing`` so untouched quarters keep their rows.
    """
    if provider is None:
        from app.stocks.libraries.yfinance import YFinance

        provider = YFinance.get_splits
    lookup = _paced(provider, PROVIDER_PACING_SECONDS)

    registry: list[dict[str, object]] = []
    for quarter in scannable_quarters(quarters):
        current = _quarter_positions(quarter)
        previous = _quarter_positions(get_previous_quarter(quarter))
        if current.empty or previous.empty:
            continue
        paired = current.merge(previous, on=["Fund", "CUSIP"], suffixes=("", "_previous"))
        registry.extend(splits_for_transition(paired, quarter, lookup))
    return registry


def unregistered_splits(
    detected: list[dict[str, object]], registry: dict[str, dict[str, float]]
) -> list[dict[str, object]]:
    """
    The detected splits the saved registry does not already record with the
    same factor. A non-empty result means comparisons were written on a stale
    registry and the affected quarters need regenerating.
    """
    return [
        split
        for split in detected
        if registry.get(str(split["Quarter"]), {}).get(str(split["CUSIP"])) != split["Factor"]
    ]


def unregistered_splits_for_quarter(
    quarter: str, registry: dict[str, dict[str, float]]
) -> list[dict[str, object]]:
    """
    Splits visible in a quarter's own filings that the registry does not
    record, so a scheduled fetch cannot quietly write comparisons against a
    stale registry.

    Deliberately provider-free: it runs on holder agreement alone, costs no
    network and so can run after every fetch. It therefore sees only the
    securities three funds hold, which makes it a warning, not a source.
    """
    current = _quarter_positions(quarter)
    previous = _quarter_positions(get_previous_quarter(quarter))
    if current.empty or previous.empty:
        return []

    paired = current.merge(previous, on=["Fund", "CUSIP"], suffixes=("", "_previous"))
    detected: list[dict[str, object]] = [
        {"Quarter": quarter, "CUSIP": cusip, "Factor": factor}
        for cusip, factor in detect_splits(paired).items()
    ]
    return unregistered_splits(detected, registry)


def _next_quarter(quarter: str) -> str:
    """
    The quarter label following a 'YYYYQN' one.
    """
    year, number = int(quarter[:4]), int(quarter[5:])
    return f"{year + 1}Q1" if number == 4 else f"{year}Q{number + 1}"


def factors_between(
    registry: dict[str, dict[str, float]],
    previous_quarter: str | None,
    current_quarter: str,
) -> dict[str, float]:
    """
    The split factors separating two filings, compounded over every quarter
    between them.

    A fund that skips a quarter is compared against two quarters back, so a
    single quarter's factors are not enough: every split in the span has to be
    applied, or the gap silently reintroduces the error this module removes.
    """
    if not previous_quarter or not registry:
        return {}

    factors: dict[str, float] = {}
    quarter = _next_quarter(previous_quarter)
    while quarter <= current_quarter:
        for cusip, factor in registry.get(quarter, {}).items():
            factors[cusip] = factors.get(cusip, 1.0) * factor
        quarter = _next_quarter(quarter)
    return factors
