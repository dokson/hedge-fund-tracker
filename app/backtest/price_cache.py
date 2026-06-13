import csv
from collections.abc import Callable
from datetime import date
from pathlib import Path

from app.utils.logger import get_logger

logger = get_logger(__name__)

CACHE_DIR = "__pricecache__"
CACHE_FILE = "prices.csv"
_FIELDNAMES = ["ticker", "date", "price"]


class PriceCache:
    """
    Persistent (ticker, date) -> price cache backing the backtest price lookups.

    Historical prices never change, so caching them makes a full regeneration
    near-instant: changing the tracked-fund list reshuffles screen membership
    but reuses every cached price, fetching only genuinely new (ticker, date)
    pairs. Misses fall through to the injected fetcher; only successful (non-None)
    lookups are persisted, so a transient failure is retried on the next run.
    """

    def __init__(
        self,
        path: Path | str | None = None,
        fetch_fn: Callable[[str, date], float | None] | None = None,
    ) -> None:
        """
        Load any existing cache file and store the fallback price fetcher.
        """
        self._path = Path(path) if path is not None else Path(CACHE_DIR) / CACHE_FILE
        self._fetch_fn = fetch_fn or self._default_fetch_fn
        self._cache: dict[tuple[str, str], float] = self._load()

    @staticmethod
    def _default_fetch_fn(ticker: str, day: date) -> float | None:
        """
        Default lookup via the project's free price-fetch chain.
        """
        from app.stocks.price_fetcher import PriceFetcher

        return PriceFetcher.get_avg_price(ticker, day)

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
                    cache[(row["ticker"], row["date"])] = float(value)
                except (ValueError, KeyError):
                    continue
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
        if price is not None:
            self._cache[key] = price
            self._append(ticker, day_iso, price)
        return price
