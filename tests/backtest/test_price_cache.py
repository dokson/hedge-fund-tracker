import tempfile
import unittest
from datetime import date
from pathlib import Path

from app.backtest.price_cache import PriceCache


def RECENT() -> date:
    """
    A "today" one day after the 2025-05-15 lookups, so their misses can still resolve.
    """
    return date(2025, 5, 16)


def LATER() -> date:
    """
    A "today" long after every lookup in these tests: their misses are settled.
    """
    return date(2026, 1, 1)


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
        self.range_calls: list[tuple[str, date, date]] = []

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

    def test_non_positive_or_non_finite_prices_are_not_persisted(self):
        """
        A zero, negative or NaN quote is a fetch failure: returned as missing, never cached.
        """
        for bad in (0.0, -1.0, float("nan"), float("inf")):
            with self.subTest(price=bad):
                calls: list[str] = []

                def fetch(ticker, _day, bad=bad, calls=calls):
                    """
                    Return the bad quote and count calls.
                    """
                    calls.append(ticker)
                    return bad

                cache = PriceCache(path=self.path, fetch_fn=fetch, today_fn=RECENT)
                self.assertIsNone(cache.get("BAD", date(2025, 5, 15)))
                self.assertIsNone(cache.get("BAD", date(2025, 5, 15)))
                self.assertEqual(len(calls), 2)
                self.assertFalse(self.path.exists())

    def test_bad_rows_already_on_disk_are_ignored(self):
        """
        Zero/NaN rows written by an older version are dropped on load and refetched.
        """
        self.path.write_text(
            'ticker,date,price\n"AAA","2025-05-15","0.0"\n"BBB","2025-05-15","nan"\n',
            encoding="utf-8",
        )
        cache = PriceCache(path=self.path, fetch_fn=self._fetch)
        self.assertEqual(cache.get("AAA", date(2025, 5, 15)), 100.0)
        self.assertEqual(cache.get("BBB", date(2025, 5, 15)), 100.0)
        self.assertEqual(len(self.calls), 2)

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

    def _fetch_range(self, ticker: str, start: date, end: date):
        """
        Record the range call and return a deterministic last bar (or None for MISS).
        """
        self.range_calls.append((ticker, start, end))
        if ticker == "MISS":
            return None
        return 42.0

    def test_range_lookup_is_persisted_and_reloaded(self):
        """
        A found last-bar price is cached per (ticker, window): a re-run is a cache hit.
        """
        start, end = date(2025, 5, 15), date(2025, 8, 14)
        cache = PriceCache(path=self.path, fetch_fn=self._fetch, range_fetch_fn=self._fetch_range)
        self.assertEqual(cache.last_in_range("GONE", start, end), 42.0)
        reloaded = PriceCache(
            path=self.path, fetch_fn=self._fetch, range_fetch_fn=self._fetch_range
        )
        self.assertEqual(reloaded.last_in_range("GONE", start, end), 42.0)
        self.assertEqual(self.range_calls, [("GONE", start, end)])
        self.assertEqual(self.calls, [])

    def test_range_key_does_not_shadow_a_daily_price(self):
        """
        A cached window price is never served as the price of a single day.
        """
        start, end = date(2025, 5, 15), date(2025, 8, 14)
        cache = PriceCache(path=self.path, fetch_fn=self._fetch, range_fetch_fn=self._fetch_range)
        cache.last_in_range("AAA", start, end)
        self.assertEqual(cache.get("AAA", end), 100.0)

    def test_range_miss_is_not_persisted(self):
        """
        A window with no bar is returned as missing and not cached.
        """
        start, end = date(2025, 5, 15), date(2025, 8, 14)
        cache = PriceCache(
            path=self.path,
            fetch_fn=self._fetch,
            range_fetch_fn=self._fetch_range,
            today_fn=lambda: date(2025, 8, 15),
        )
        self.assertIsNone(cache.last_in_range("MISS", start, end))
        self.assertFalse(self.path.exists())

    def test_none_result_is_not_persisted(self):
        """
        A failed lookup (None) on a recent date is returned but not cached, so it is retried.
        """
        cache = PriceCache(path=self.path, fetch_fn=self._fetch, today_fn=RECENT)
        self.assertIsNone(cache.get("MISS", date(2025, 5, 15)))
        self.assertIsNone(cache.get("MISS", date(2025, 5, 15)))
        self.assertEqual(len(self.calls), 2)

    def test_settled_miss_is_remembered_across_runs(self):
        """
        A price still missing weeks later is recorded, so a new run never refetches it.
        """
        first = PriceCache(path=self.path, fetch_fn=self._fetch, today_fn=LATER)
        self.assertIsNone(first.get("MISS", date(2025, 5, 15)))
        second = PriceCache(path=self.path, fetch_fn=self._fetch, today_fn=LATER)
        self.assertIsNone(second.get("MISS", date(2025, 5, 15)))
        self.assertEqual(len(self.calls), 1)

    def test_settled_range_miss_is_remembered(self):
        """
        A window with no bar, closed weeks ago, is not asked again.
        """
        start, end = date(2025, 5, 15), date(2025, 8, 14)
        for _ in range(2):
            cache = PriceCache(
                path=self.path,
                fetch_fn=self._fetch,
                range_fetch_fn=self._fetch_range,
                today_fn=LATER,
            )
            self.assertIsNone(cache.last_in_range("MISS", start, end))
        self.assertEqual(len(self.range_calls), 1)

    def test_recorded_miss_never_reads_as_a_price(self):
        """
        A miss row on disk does not shadow or fake a valid price for another key.
        """
        PriceCache(path=self.path, fetch_fn=self._fetch, today_fn=LATER).get(
            "MISS", date(2025, 5, 15)
        )
        cache = PriceCache(path=self.path, fetch_fn=self._fetch, today_fn=LATER)
        self.assertEqual(cache.get("AAA", date(2025, 5, 15)), 100.0)


if __name__ == "__main__":
    unittest.main()
