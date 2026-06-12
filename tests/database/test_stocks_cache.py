import unittest
from pathlib import Path
from unittest.mock import patch

import pandas as pd

from app.database.stocks import load_stocks

_CSV = 'CUSIP,Ticker,Company,Industry\n"000000001","AAA","Alpha Co","Tech"\n'


class TestLoadStocksCache(unittest.TestCase):
    def setUp(self):
        """
        Reset the module cache and route reads to a real temp file.
        """
        import tempfile

        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.path = Path(self._tmp.name) / "stocks.csv"
        self.path.write_text(_CSV, encoding="utf-8")
        load_stocks.cache_clear()
        self.addCleanup(load_stocks.cache_clear)

    def test_unchanged_file_is_parsed_once(self):
        """
        Repeated calls with no file change parse the CSV only once.
        """
        with patch("app.database.stocks.pd.read_csv", wraps=pd.read_csv) as spy:
            first = load_stocks(str(self.path))
            second = load_stocks(str(self.path))

        self.assertEqual(spy.call_count, 1)
        self.assertEqual(first.loc["000000001", "Ticker"], "AAA")
        self.assertEqual(second.loc["000000001", "Ticker"], "AAA")

    def test_cache_returns_independent_copies(self):
        """
        Callers can mutate the returned frame without poisoning the cache.
        """
        first = load_stocks(str(self.path))
        first.loc["000000001", "Ticker"] = "ZZZ"
        second = load_stocks(str(self.path))

        self.assertEqual(second.loc["000000001", "Ticker"], "AAA")

    def test_file_change_invalidates_cache(self):
        """
        A newer modification time forces a re-read.
        """
        import os

        load_stocks(str(self.path))
        self.path.write_text(_CSV + '"000000002","BBB","Beta Co","Health"\n', encoding="utf-8")
        # Force a strictly newer mtime regardless of filesystem resolution.
        stat = self.path.stat()
        os.utime(self.path, (stat.st_atime, stat.st_mtime + 10))

        result = load_stocks(str(self.path))

        self.assertIn("000000002", result.index)

    def test_size_change_invalidates_even_with_same_mtime(self):
        """
        Rapid successive writes can share an mtime tick (coarse filesystem
        resolution). A changed byte count must still force a re-read, or a
        concurrent append would be served stale.
        """
        import os

        load_stocks(str(self.path))
        original_mtime = self.path.stat().st_mtime_ns
        self.path.write_text(_CSV + '"000000002","BBB","Beta Co","Health"\n', encoding="utf-8")
        # Pin the mtime back to the pre-write value to isolate size-based invalidation.
        os.utime(self.path, ns=(original_mtime, original_mtime))

        result = load_stocks(str(self.path))

        self.assertIn("000000002", result.index)


if __name__ == "__main__":
    unittest.main()
