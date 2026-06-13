import tempfile
import unittest
from datetime import date
from pathlib import Path

from app.backtest.price_cache import PriceCache


class TestPriceCache(unittest.TestCase):
    """
    Tests for the persistent (ticker, date) -> price cache.
    """

    def setUp(self):
        """
        Create a temporary cache file path and a counting fake fetcher.
        """
        self.tmp = tempfile.mkdtemp(prefix="hft_price_cache_")
        self.path = Path(self.tmp) / "prices.csv"
        self.calls: list[tuple[str, date]] = []

    def tearDown(self):
        """
        Remove the temporary directory.
        """
        import shutil

        shutil.rmtree(self.tmp, ignore_errors=True)

    def _fetch(self, ticker: str, day: date):
        """
        Record the call and return a deterministic price (or None for MISS).
        """
        self.calls.append((ticker, day))
        if ticker == "MISS":
            return None
        return 100.0

    def test_miss_fetches_and_persists(self):
        """
        A cache miss calls the fetcher, returns the value, and writes it to disk.
        """
        cache = PriceCache(path=self.path, fetch_fn=self._fetch)
        price = cache.get("AAA", date(2025, 5, 15))
        self.assertEqual(price, 100.0)
        self.assertEqual(len(self.calls), 1)
        self.assertTrue(self.path.exists())

    def test_hit_does_not_refetch(self):
        """
        A second lookup of the same (ticker, date) is served from memory.
        """
        cache = PriceCache(path=self.path, fetch_fn=self._fetch)
        cache.get("AAA", date(2025, 5, 15))
        cache.get("AAA", date(2025, 5, 15))
        self.assertEqual(len(self.calls), 1)

    def test_persisted_cache_reloads_without_fetch(self):
        """
        A fresh instance over the same file returns cached prices with no fetch.
        """
        PriceCache(path=self.path, fetch_fn=self._fetch).get("AAA", date(2025, 5, 15))
        self.calls.clear()
        reloaded = PriceCache(path=self.path, fetch_fn=self._fetch)
        price = reloaded.get("AAA", date(2025, 5, 15))
        self.assertEqual(price, 100.0)
        self.assertEqual(len(self.calls), 0)

    def test_none_result_is_not_persisted(self):
        """
        A failed lookup (None) is returned but not cached, so it is retried.
        """
        cache = PriceCache(path=self.path, fetch_fn=self._fetch)
        self.assertIsNone(cache.get("MISS", date(2025, 5, 15)))
        self.assertIsNone(cache.get("MISS", date(2025, 5, 15)))
        self.assertEqual(len(self.calls), 2)


if __name__ == "__main__":
    unittest.main()
