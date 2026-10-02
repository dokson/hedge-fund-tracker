"""
The full-file writers honour the same per-file lock as the in-place rewriters,
so a ticker cascade and a fetch can't overwrite each other's changes.
"""

import shutil
import tempfile
import threading
import time
import unittest
from pathlib import Path
from unittest.mock import patch

import pandas as pd

from app.database.locks import file_lock
from app.database.quarters import (
    read_non_quarterly_rows,
    save_comparison,
    save_non_quarterly_filings,
    write_non_quarterly_filings,
)


class WriterLockTest(unittest.TestCase):
    """
    save_non_quarterly_filings and save_comparison wait for a held file lock.
    """

    def setUp(self):
        """
        Point the database at a temporary folder.
        """
        self.root = Path(tempfile.mkdtemp())
        self._db = patch("app.database.DB_FOLDER", str(self.root))
        self._db.start()

    def tearDown(self):
        """
        Restore the database folder and remove the temporary one.
        """
        self._db.stop()
        shutil.rmtree(self.root, ignore_errors=True)

    def _assert_waits_for_lock(self, target: Path, run) -> None:
        """
        Runs ``run`` while ``<target>.lock`` is held and checks that ``target``
        is only written after the lock is released.
        """
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text("original\n", encoding="utf-8")
        lock_path = target.with_name(f"{target.name}.lock")
        lock_path.touch()
        worker = threading.Thread(target=run)
        worker.start()
        try:
            time.sleep(0.4)
            self.assertEqual(target.read_text(encoding="utf-8"), "original\n")
        finally:
            lock_path.unlink()
            worker.join(timeout=10)
        self.assertFalse(worker.is_alive())
        self.assertNotEqual(target.read_text(encoding="utf-8"), "original\n")

    def test_save_non_quarterly_filings_waits_for_the_file_lock(self):
        """
        A concurrent holder of the non_quarterly.csv lock delays the save.
        """
        rows = pd.DataFrame(
            {"Date": ["2025-01-02"], "Filing_Date": ["2025-01-03"], "Fund": ["A"], "Ticker": ["T"]}
        )
        self._assert_waits_for_lock(
            self.root / "non_quarterly.csv", lambda: save_non_quarterly_filings([rows])
        )

    def test_inner_writer_runs_under_an_outer_lock(self):
        """
        The lock-free writer can rewrite the file while the caller holds its lock.
        """
        target = self.root / "non_quarterly.csv"
        rows = pd.DataFrame(
            {"Date": ["2025-01-02"], "Filing_Date": ["2025-01-03"], "Fund": ["A"], "Ticker": ["T"]}
        )
        with file_lock(target, timeout=1):
            write_non_quarterly_filings([rows], str(target))
        self.assertEqual(read_non_quarterly_rows(str(target))["Ticker"].tolist(), ["T"])

    def test_read_rows_distinguishes_missing_from_unreadable(self):
        """
        A missing file is empty; an unreadable one raises instead of looking empty.
        """
        self.assertTrue(read_non_quarterly_rows(str(self.root / "absent.csv")).empty)
        with self.assertRaises(Exception):
            read_non_quarterly_rows(str(self.root))

    def test_save_comparison_waits_for_the_file_lock(self):
        """
        A concurrent holder of a quarter file's lock delays the comparison write.
        """
        comparison = pd.DataFrame({"CUSIP": ["C1"], "Ticker": ["T"], "Shares": [1]})
        self._assert_waits_for_lock(
            self.root / "2025Q1" / "Fund_A.csv",
            lambda: save_comparison(comparison, "2025-03-31", "Fund A"),
        )


if __name__ == "__main__":
    unittest.main()
