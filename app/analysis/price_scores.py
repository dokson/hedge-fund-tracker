"""
Momentum and low-volatility scores computed from daily price history.

Momentum is the "12-1" price return: the close 21 trading days ago over the close
252 trading days ago, minus one. With 126-252 closes the lookback starts at the
oldest available close instead. Volatility is the sample standard deviation of
daily log returns over the last 252 returns, annualized by sqrt(252). Fewer than
126 closes is treated as insufficient history.

Both metrics become cross-sectional percentiles mapped onto integers 1-100.
"""

import math
import statistics
import time
from collections.abc import Callable, Mapping, Sequence
from concurrent.futures import ThreadPoolExecutor

from app.stocks.libraries import YFinance
from app.utils.logger import get_logger, log_safe

logger = get_logger(__name__)

TRADING_DAYS = 252
SKIP_DAYS = 21
MIN_HISTORY = 126
NEUTRAL_SCORE = 50
HISTORY_PERIOD = "2y"

MAX_WORKERS = 2
PAUSE_SECONDS = 0.5
BACKOFF_SECONDS = 2.0
MAX_ATTEMPTS = 3

Closes = list[float] | None


def momentum_12_1(closes: Sequence[float]) -> float | None:
    """
    Return the 12-1 momentum of a daily close series, oldest first.

    Returns None when fewer than MIN_HISTORY closes are available.
    """
    n = len(closes)
    if n < MIN_HISTORY:
        return None
    base = closes[max(0, n - 1 - TRADING_DAYS)]
    recent = closes[n - 1 - SKIP_DAYS]
    if base <= 0:
        return None
    return recent / base - 1


def annualized_volatility(closes: Sequence[float]) -> float | None:
    """
    Return the annualized volatility of daily log returns over the last year.

    Returns None when fewer than MIN_HISTORY closes are available.
    """
    if len(closes) < MIN_HISTORY or any(c <= 0 for c in closes):
        return None
    window = closes[-(TRADING_DAYS + 1) :]
    returns = [math.log(b / a) for a, b in zip(window, window[1:], strict=False)]
    return statistics.stdev(returns) * math.sqrt(TRADING_DAYS)


def percentile_scores(values: Mapping[str, float | None], higher_is_better: bool) -> dict[str, int]:
    """
    Map values onto 1-100 by cross-sectional rank.

    Ties share their average rank and the score is linear in rank, rounded half up.
    Missing values, a single ranked value, or no dispersion score NEUTRAL_SCORE.
    """
    scores = dict.fromkeys(values, NEUTRAL_SCORE)
    ranked = {k: (v if higher_is_better else -v) for k, v in values.items() if v is not None}
    n = len(ranked)
    if n < 2 or len(set(ranked.values())) == 1:
        return scores
    ordered = sorted(ranked.values())
    for key, value in ranked.items():
        first = ordered.index(value)
        count = ordered.count(value)
        rank = first + (count + 1) / 2
        scores[key] = math.floor(1 + 99 * (rank - 1) / (n - 1) + 0.5)
    return scores


def score_histories(histories: Mapping[str, Closes]) -> dict[str, dict]:
    """
    Compute raw metrics and 1-100 scores for every ticker's close series.

    Each value holds ``Momentum``, ``Volatility`` (None when unavailable),
    ``Momentum_Score`` and ``Low_Volatility_Score``.
    """
    momentum: dict[str, float | None] = {}
    volatility: dict[str, float | None] = {}
    for ticker, closes in histories.items():
        if not closes or len(closes) < MIN_HISTORY:
            logger.warning(
                "Insufficient price history for %s (%d closes): neutral momentum/volatility",
                log_safe(ticker),
                len(closes or []),
            )
            momentum[ticker] = volatility[ticker] = None
            continue
        momentum[ticker] = momentum_12_1(closes)
        volatility[ticker] = annualized_volatility(closes)

    momentum_scores = percentile_scores(momentum, higher_is_better=True)
    volatility_scores = percentile_scores(volatility, higher_is_better=False)
    return {
        ticker: {
            "Momentum": momentum[ticker],
            "Volatility": volatility[ticker],
            "Momentum_Score": momentum_scores[ticker],
            "Low_Volatility_Score": volatility_scores[ticker],
        }
        for ticker in histories
    }


def _yfinance_closes(ticker: str) -> Closes:
    """
    Fetch daily closes, oldest first, from YFinance.
    """
    points = YFinance.get_history(ticker, HISTORY_PERIOD)
    if not points:
        return None
    return [float(p["close"]) for p in points]


def fetch_daily_closes(
    tickers: Sequence[str],
    fetch_fn: Callable[[str], Closes] = _yfinance_closes,
    sleep: Callable[[float], None] = time.sleep,
) -> dict[str, Closes]:
    """
    Fetch daily closes for a short ticker list, paced and at most MAX_WORKERS at once.

    An empty result or an exception is retried with exponential backoff (the
    provider degrades to empty responses when rate limited); after MAX_ATTEMPTS
    the ticker maps to None and the others proceed.
    """

    def fetch_one(ticker: str) -> Closes:
        """
        Fetch one ticker with pacing and backoff.
        """
        sleep(PAUSE_SECONDS)
        for attempt in range(1, MAX_ATTEMPTS + 1):
            try:
                closes = fetch_fn(ticker)
                if closes:
                    return closes
            except Exception:
                logger.debug("Price history fetch failed for %s", log_safe(ticker), exc_info=True)
            if attempt < MAX_ATTEMPTS:
                sleep(BACKOFF_SECONDS * 2 ** (attempt - 1))
        logger.warning("No price history for %s", log_safe(ticker))
        return None

    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as pool:
        return dict(zip(tickers, pool.map(fetch_one, tickers), strict=True))


def compute_price_scores(tickers: Sequence[str]) -> dict[str, dict]:
    """
    Fetch price history for ``tickers`` and score momentum and low volatility.
    """
    logger.progress("Fetching price history for %d tickers...", len(tickers))
    return score_histories(fetch_daily_closes(tickers))
