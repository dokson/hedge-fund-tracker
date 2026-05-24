import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from app.utils.version import get_version


class TestVersion(unittest.TestCase):
    def setUp(self):
        """
        Clears the lru_cache so each test reads the helper from scratch.
        """
        get_version.cache_clear()

    def tearDown(self):
        """
        Restores cache state so other tests in the suite see a clean read.
        """
        get_version.cache_clear()

    def test_reads_version_from_package_json(self):
        """
        Returns the value of the `version` field declared in
        app/frontend/package.json — the canonical source-of-truth for the
        whole repo.
        """
        repo_root = Path(__file__).resolve().parents[2]
        with (repo_root / "app" / "frontend" / "package.json").open(encoding="utf-8") as f:
            expected = json.load(f)["version"]
        self.assertEqual(get_version(), expected)

    def test_returns_fallback_when_package_json_missing(self):
        """
        Degrades to "0.0.0" when the package.json cannot be located (e.g. a
        stripped-down deployment without frontend artefacts).
        """
        with patch("app.utils.version._PACKAGE_JSON", Path("/nonexistent/package.json")):
            self.assertEqual(get_version(), "0.0.0")

    def _write_tmp_json(self, content: str) -> Path:
        """
        Writes the given raw string to a temp file and returns its Path.
        """
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".json", delete=False, encoding="utf-8"
        ) as tmp:
            tmp.write(content)
            return Path(tmp.name)

    def test_returns_fallback_when_package_json_is_malformed(self):
        """
        Degrades to "0.0.0" when the package.json is not valid JSON.
        """
        tmp_path = self._write_tmp_json("{ not json")
        try:
            with patch("app.utils.version._PACKAGE_JSON", tmp_path):
                self.assertEqual(get_version(), "0.0.0")
        finally:
            tmp_path.unlink(missing_ok=True)

    def test_returns_fallback_when_version_field_missing(self):
        """
        Degrades to "0.0.0" when the JSON is valid but lacks a `version` key.
        """
        tmp_path = self._write_tmp_json(json.dumps({"name": "hedge-fund-tracker"}))
        try:
            with patch("app.utils.version._PACKAGE_JSON", tmp_path):
                self.assertEqual(get_version(), "0.0.0")
        finally:
            tmp_path.unlink(missing_ok=True)

    def test_returns_fallback_when_version_is_empty_string(self):
        """
        Degrades to "0.0.0" when the version field is present but empty.
        """
        tmp_path = self._write_tmp_json(json.dumps({"version": "   "}))
        try:
            with patch("app.utils.version._PACKAGE_JSON", tmp_path):
                self.assertEqual(get_version(), "0.0.0")
        finally:
            tmp_path.unlink(missing_ok=True)

    def test_caches_result_across_calls(self):
        """
        get_version is cached via lru_cache, so repeated calls hit the file
        system only once per process.
        """
        first = get_version()
        second = get_version()
        self.assertIs(first, second)


if __name__ == "__main__":
    unittest.main()
