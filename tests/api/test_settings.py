import shutil
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from fastapi.testclient import TestClient

from app.server import app

client = TestClient(app)


class TestEnvEndpoints(unittest.TestCase):
    """/api/settings/env read + overwrite, against a temp .env."""

    def setUp(self):
        """Use an isolated temp directory so the real .env is never touched."""
        self._tmp = tempfile.mkdtemp(prefix="hft_env_")
        self.env = Path(self._tmp) / ".env"

    def tearDown(self):
        """Remove the temp directory."""
        shutil.rmtree(self._tmp, ignore_errors=True)

    def test_get_env_parses_pairs_and_skips_comments(self):
        """Comment and blank lines are skipped; key=value pairs are parsed."""
        self.env.write_text("KEY=val\n# a comment\n\nFOO=bar\n", encoding="utf-8")
        with patch("app.api.settings.ENV_FILE", self.env):
            resp = client.get("/api/settings/env")
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.json(), {"KEY": "val", "FOO": "bar"})

    def test_get_env_missing_file_returns_empty(self):
        """A missing .env yields an empty object, not an error."""
        with patch("app.api.settings.ENV_FILE", self.env):
            resp = client.get("/api/settings/env")
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.json(), {})

    def test_put_env_writes_pairs(self):
        """PUT serialises the JSON object back to KEY=value lines."""
        with patch("app.api.settings.ENV_FILE", self.env):
            resp = client.put("/api/settings/env", json={"A": "1", "B": "2"})
        self.assertEqual(resp.status_code, 200)
        written = self.env.read_text(encoding="utf-8")
        self.assertIn("A=1", written)
        self.assertIn("B=2", written)


if __name__ == "__main__":
    unittest.main()
