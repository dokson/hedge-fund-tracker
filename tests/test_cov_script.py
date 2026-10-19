"""
Tests for scripts.cov, the cross-platform coverage runner behind ``pipenv run cov``.
"""

import subprocess
import unittest
from unittest.mock import MagicMock

from scripts.cov import main


def _completed(code: int) -> subprocess.CompletedProcess:
    """
    Build a finished process with the given exit code.
    """
    return subprocess.CompletedProcess(args=[], returncode=code)


class TestCovScript(unittest.TestCase):
    """
    The runner measures the unittest suite, then reports, without any shell.
    """

    def test_failing_tests_skip_report_and_propagate_exit_code(self):
        """
        A red test run returns its exit code and prints no report.
        """
        run = MagicMock(return_value=_completed(1))

        self.assertEqual(main(run=run), 1)
        run.assert_called_once()


if __name__ == "__main__":
    unittest.main()
