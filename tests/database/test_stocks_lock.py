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


if __name__ == "__main__":
    unittest.main()
