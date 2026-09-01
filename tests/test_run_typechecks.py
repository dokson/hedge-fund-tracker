"""
Tests for the pre-push bootstrap helper in scripts/run_typechecks.py.
"""

import ast
import sys
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from scripts.run_typechecks import (  # noqa: E402
    _pipenv_candidates,
    _project_python_version,
)

_REPO_ROOT = Path(__file__).resolve().parents[1]


class TestProjectPythonVersion(unittest.TestCase):
    """
    The launcher pin must be derived from the Pipfile, never hardcoded.
    """

    def _write_pipfile(self, directory: str, version: str) -> Path:
        """
        Write a minimal Pipfile declaring `version` and return its path.
        """
        path = Path(directory) / "Pipfile"
        path.write_text(
            f'[[source]]\nurl = "https://pypi.org/simple"\n\n'
            f'[requires]\npython_version = "{version}"\n',
            encoding="utf-8",
        )
        return path

    def test_reads_version_from_pipfile(self):
        """
        A bumped Pipfile must change the resolved version, with no code edit.
        """
        with TemporaryDirectory() as tmp:
            pipfile = self._write_pipfile(tmp, "3.99")
            self.assertEqual(_project_python_version(pipfile), "3.99")

    def test_matches_the_real_pipfile(self):
        """
        The repo's own Pipfile resolves, so the hook targets the real venv.
        """
        pipfile = _REPO_ROOT / "Pipfile"
        expected = None
        for line in pipfile.read_text(encoding="utf-8").splitlines():
            if line.strip().startswith("python_version"):
                expected = line.split("=", 1)[1].strip().strip('"')
                break

        self.assertIsNotNone(expected, "Pipfile declares no python_version")
        self.assertEqual(_project_python_version(pipfile), expected)

    def test_falls_back_when_pipfile_is_unreadable(self):
        """
        A missing Pipfile must not crash the hook; the pin is simply omitted.
        """
        with TemporaryDirectory() as tmp:
            self.assertIsNone(_project_python_version(Path(tmp) / "absent"))

    def test_candidates_include_versioned_launcher(self):
        """
        The launcher candidate carries the Pipfile version when one resolves.
        """
        with TemporaryDirectory() as tmp:
            pipfile = self._write_pipfile(tmp, "3.99")
            self.assertIn(["py", "-3.99", "-m", "pipenv"], _pipenv_candidates(pipfile))

    def test_candidates_omit_versioned_launcher_without_pipfile(self):
        """
        With no Pipfile, no bogus `py -None` candidate is produced.
        """
        with TemporaryDirectory() as tmp:
            candidates = _pipenv_candidates(Path(tmp) / "absent")

        self.assertTrue(all("None" not in part for c in candidates for part in c))
        self.assertIn(["pipenv"], candidates)


class TestBootstrapCompatibility(unittest.TestCase):
    """
    The hook runs this file with the ambient interpreter, not the project venv.
    """

    def test_parses_without_project_only_syntax(self):
        """
        Reject syntax the ambient interpreter may not support (PEP 758).
        """
        source = (_REPO_ROOT / "scripts" / "run_typechecks.py").read_text(encoding="utf-8")
        tree = ast.parse(source, feature_version=(3, 9))

        for node in ast.walk(tree):
            if isinstance(node, ast.ExceptHandler) and isinstance(node.type, ast.Tuple):
                self.assertTrue(
                    source.splitlines()[node.lineno - 1]
                    .split("except", 1)[1]
                    .lstrip()
                    .startswith("("),
                    "multi-exception except clauses must stay parenthesized",
                )


if __name__ == "__main__":
    unittest.main()
