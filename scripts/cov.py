"""
Run the Python test suite under coverage, then print the report.

Cross-platform replacement for a ``sh -c '... && ...'`` Pipfile script, which
fails on Windows where no POSIX shell is on PATH.
"""

import subprocess
import sys
from collections.abc import Callable

_TEST_CMD = [sys.executable, "-m", "coverage", "run", "-m", "unittest", "discover"]
_REPORT_CMD = [sys.executable, "-m", "coverage", "report"]


def main(run: Callable[..., subprocess.CompletedProcess] = subprocess.run) -> int:
    """
    Measure the unittest suite and report coverage; a failing suite skips the report.
    """
    tests = run(_TEST_CMD, check=False)
    if tests.returncode != 0:
        return tests.returncode
    return run(_REPORT_CMD, check=False).returncode


if __name__ == "__main__":
    sys.exit(main())
