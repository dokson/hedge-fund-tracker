import csv
import math
from collections.abc import Callable
from datetime import date, timedelta
from pathlib import Path
from typing import TypeIs

from app.utils.logger import get_logger

logger = get_logger(__name__)

CACHE_DIR = "__pricecache__"
CACHE_FILE = "prices.csv"
_FIELDNAMES = ["ticker", "date", "price"]
# A lookup still empty this long after its date is treated as permanent (a
# delisted or unknown symbol), recorded as a blank-price row and never retried.
MISS_SETTLE_DAYS = 7


def _is_valid_price(price: float | None) -> TypeIs[float]:
    """
    True for a finite, strictly positive quote; anything else is a failed lookup.
    """
    return price is not None and math.isfinite(price) and price > 0


class PriceCache:
    """
    Persistent (ticker, date) -> price cache backing the backtest price lookups.

    Historical prices never change, so caching them makes a full regeneration
    near-instant: changing the tracked-fund list reshuffles screen membership
    but reuses every cached price, fetching only genuinely new (ticker, date)
    pairs. Misses fall through to the injected fetcher. A failed lookup for a
    date older than MISS_SETTLE_DAYS is recorded too (blank price), because a
    historical price that no provider has will not appear later; a recent miss
    is retried on the next run.
    """

    def __init__(
        self,
        path: Path | str | None = None,
        fetch_fn: Callable[[str, date], float | None] | None = None,
        range_fetch_fn: Callable[[str, date, date], float | None] | None = None,
        today_fn: Callable[[], date] = date.today,
    ) -> None:
        """
        Load any existing cache file and store the fallback price fetchers.
        """
        self._path = Path(path) if path is not None else Path(CACHE_DIR) / CACHE_FILE
        self._fetch_fn = fetch_fn or self._default_fetch_fn
        self._range_fetch_fn = range_fetch_fn or self._default_range_fetch_fn
        self._today_fn = today_fn
        self._misses: set[tuple[str, str]] = set()
        self._cache: dict[tuple[str, str], float] = self._load()

    @staticmethod
    def _default_fetch_fn(ticker: str, day: date) -> float | None:
        """
        Default lookup via the project's free price-fetch chain.
        """
        from app.stocks.price_fetcher import PriceFetcher

        return PriceFetcher.get_avg_price(ticker, day)

    @staticmethod
    def _default_range_fetch_fn(ticker: str, start: date, end: date) -> float | None:
        """
        Default last-bar-in-range lookup via the project's free price-fetch chain.
        """
        from app.stocks.price_fetcher import PriceFetcher

        return PriceFetcher.get_last_price_in_range(ticker, start, end)

    def _load(self) -> dict[tuple[str, str], float]:
        """
        Read the persisted cache file into memory, skipping malformed rows.
        """
        cache: dict[tuple[str, str], float] = {}
        if not self._path.exists():
            return cache
        with self._path.open(newline="", encoding="utf-8") as handle:
            for row in csv.DictReader(handle):
                value = row.get("price")
                if value == "" and row.get("ticker") and row.get("date"):
                    self._misses.add((row["ticker"], row["date"]))
                    continue
                if not value:
                    continue
                try:
                    price = float(value)
                    key = (row["ticker"], row["date"])
                except ValueError, KeyError:
                    continue
                if _is_valid_price(price):
                    cache[key] = price
        return cache

    def _append(self, ticker: str, day_iso: str, price: float | None) -> None:
        """
        Append one resolved price, or a blank settled miss, to the on-disk cache.
        """
        self._path.parent.mkdir(parents=True, exist_ok=True)
        write_header = not self._path.exists()
        with self._path.open("a", newline="", encoding="utf-8") as handle:
            writer = csv.DictWriter(handle, fieldnames=_FIELDNAMES, quoting=csv.QUOTE_ALL)
            if write_header:
                writer.writeheader()
            writer.writerow(
                {"ticker": ticker, "date": day_iso, "price": "" if price is None else price}
            )

    def _record_miss(self, ticker: str, key_day: str, last_day: date) -> None:
        """
        Remember a failed lookup once its date is old enough to be final.
        """
        if (self._today_fn() - last_day) <= timedelta(days=MISS_SETTLE_DAYS):
            return
        self._misses.add((ticker, key_day))
        self._append(ticker, key_day, None)

    def get(self, ticker: str, day: date) -> float | None:
        """
        Return the price for (ticker, day), using the cache before fetching.
        """
        day_iso = day.isoformat()
        key = (ticker, day_iso)
        if key in self._cache:
            return self._cache[key]
        if key in self._misses:
            return None
        price = self._fetch_fn(ticker, day)
        if not _is_valid_price(price):
            self._record_miss(ticker, day_iso, day)
            return None
        self._cache[key] = price
        self._append(ticker, day_iso, price)
        return price

    def last_in_range(self, ticker: str, start: date, end: date) -> float | None:
        """
        Return the last bar's price in (start, end], cached per (ticker, window).
        """
        # The window key never parses as a date, so it cannot shadow a daily price.
        key_day = f"{start.isoformat()}..{end.isoformat()}"
        key = (ticker, key_day)
        if key in self._cache:
            return self._cache[key]
        if key in self._misses:
            return None
        price = self._range_fetch_fn(ticker, start, end)
        if not _is_valid_price(price):
            self._record_miss(ticker, key_day, end)
            return None
        self._cache[key] = price
        self._append(ticker, key_day, price)
        return price
