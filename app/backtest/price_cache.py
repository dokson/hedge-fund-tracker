import csv
import math
from collections.abc import Callable
from datetime import date
from pathlib import Path
from typing import TypeIs

from app.utils.logger import get_logger

logger = get_logger(__name__)

CACHE_DIR = "__pricecache__"
CACHE_FILE = "prices.csv"
_FIELDNAMES = ["ticker", "date", "price"]


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
    pairs. Misses fall through to the injected fetcher; only valid (finite, > 0)
    lookups are persisted, so a transient failure is retried on the next run.
    """

    def __init__(
        self,
        path: Path | str | None = None,
        fetch_fn: Callable[[str, date], float | None] | None = None,
        range_fetch_fn: Callable[[str, date, date], float | None] | None = None,
    ) -> None:
        """
        Load any existing cache file and store the fallback price fetchers.
        """
        self._path = Path(path) if path is not None else Path(CACHE_DIR) / CACHE_FILE
        self._fetch_fn = fetch_fn or self._default_fetch_fn
        self._range_fetch_fn = range_fetch_fn or self._default_range_fetch_fn
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

    def _append(self, ticker: str, day_iso: str, price: float) -> None:
        """
        Append a single resolved price to the on-disk cache (creating it first).
        """
        self._path.parent.mkdir(parents=True, exist_ok=True)
        write_header = not self._path.exists()
        with self._path.open("a", newline="", encoding="utf-8") as handle:
            writer = csv.DictWriter(handle, fieldnames=_FIELDNAMES, quoting=csv.QUOTE_ALL)
            if write_header:
                writer.writeheader()
            writer.writerow({"ticker": ticker, "date": day_iso, "price": price})

    def get(self, ticker: str, day: date) -> float | None:
        """
        Return the price for (ticker, day), using the cache before fetching.
        """
        day_iso = day.isoformat()
        key = (ticker, day_iso)
        if key in self._cache:
            return self._cache[key]
        price = self._fetch_fn(ticker, day)
        if not _is_valid_price(price):
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
        price = self._range_fetch_fn(ticker, start, end)
        if not _is_valid_price(price):
            return None
        self._cache[key] = price
        self._append(ticker, key_day, price)
        return price
