import os
import tempfile
import time
import unittest
from pathlib import Path
from unittest.mock import patch

import app.database as _db
from app.database import stocks_lock


class TestStocksLock(unittest.TestCase):
    def setUp(self):
        """
        Point DB_FOLDER at a temp directory so lock files never touch the real database.
        """
        self._tmp = tempfile.TemporaryDirectory()
        patcher = patch.object(_db, "DB_FOLDER", self._tmp.name)
        patcher.start()
        self.addCleanup(patcher.stop)
        self.addCleanup(self._tmp.cleanup)
        self.lock_path = Path(self._tmp.name) / f"{_db.STOCKS_FILE}.lock"

    def test_acquire_and_release(self):
        """
        The lock file exists while held and is removed on exit.
        """
        with stocks_lock(timeout=2):
            self.assertTrue(self.lock_path.exists())
        self.assertFalse(self.lock_path.exists())

    def test_nested_acquisition_times_out_instead_of_deadlocking(self):
        """
        Re-entering the non-reentrant in-process lock raises TimeoutError within the timeout.
        """
        started = time.monotonic()
        with stocks_lock(timeout=0.3), self.assertRaises(TimeoutError), stocks_lock(timeout=0.3):
            pass
        self.assertLess(time.monotonic() - started, 5)

    def test_nested_file_lock_times_out_instead_of_deadlocking(self):
        """
        A nested file_lock on the same path raises TimeoutError instead of hanging.
        """
        from app.database.locks import file_lock

        target = Path(self._tmp.name) / "non_quarterly.csv"
        started = time.monotonic()
        with file_lock(target, timeout=0.3), self.assertRaises(TimeoutError):
            with file_lock(target, timeout=0.3):
                pass
        self.assertLess(time.monotonic() - started, 5)

    def test_stale_lock_is_reclaimed_without_leftovers(self):
        """
        A lock file older than the staleness threshold is reclaimed, the lock
        is acquired, and no temporary reclaim artifacts remain afterwards.
        """
        self.lock_path.touch()
        stale_time = time.time() - 120
        os.utime(self.lock_path, (stale_time, stale_time))

        with stocks_lock(timeout=2):
            self.assertTrue(self.lock_path.exists())

        leftovers = list(Path(self._tmp.name).glob(f"{_db.STOCKS_FILE}.lock*"))
        self.assertEqual(leftovers, [])

    def test_fresh_lock_times_out(self):
        """
        A recently created lock owned by another process is honored: the
        caller times out instead of stealing it.
        """
        self.lock_path.touch()

        with self.assertRaises(TimeoutError):
            with stocks_lock(timeout=1):
                pass

        self.assertTrue(self.lock_path.exists())


class TestDbFolderAnchoring(unittest.TestCase):
    def test_default_db_folder_is_repo_absolute_regardless_of_cwd(self):
        """
        The default DB_FOLDER names <repo>/database even when the process runs elsewhere.
        """
        import importlib

        repo_db = (Path(__file__).resolve().parents[2] / "database").resolve()
        original_cwd = Path.cwd()
        with tempfile.TemporaryDirectory() as tmp:
            os.chdir(tmp)
            try:
                reloaded = importlib.reload(_db)
                folder = Path(reloaded.DB_FOLDER)
            finally:
                os.chdir(original_cwd)
                importlib.reload(_db)
        self.assertTrue(folder.is_absolute())
        self.assertEqual(folder.resolve(), repo_db)


if __name__ == "__main__":
    unittest.main()
