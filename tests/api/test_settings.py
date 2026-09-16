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
        self.env.write_text("GROQ_API_KEY=val\n# a comment\n\nFMP_API_KEY=bar\n", encoding="utf-8")
        with patch("app.api.settings.ENV_FILE", self.env):
            resp = client.get("/api/settings/env")
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.json(), {"GROQ_API_KEY": "val", "FMP_API_KEY": "bar"})

    def test_get_env_never_exposes_deployment_secrets(self):
        """
        The page manages provider keys only. Shipping the KEK or the DB password
        to a browser would put them in the DOM, DevTools and any XSS payload.
        """
        self.env.write_text(
            "MASTER_KEY=kek-value\n"
            "POSTGRES_PASSWORD=db-value\n"
            "RESET_PASSWORD_TOKEN_SECRET=reset-value\n"
            "VERIFICATION_TOKEN_SECRET=verify-value\n"
            "GROQ_API_KEY=provider-value\n",
            encoding="utf-8",
        )
        with patch("app.api.settings.ENV_FILE", self.env):
            resp = client.get("/api/settings/env")
        self.assertEqual(resp.json(), {"GROQ_API_KEY": "provider-value"})

    def test_get_env_missing_file_returns_empty(self):
        """A missing .env yields an empty object, not an error."""
        with patch("app.api.settings.ENV_FILE", self.env):
            resp = client.get("/api/settings/env")
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.json(), {})

    def test_put_env_writes_pairs(self):
        """PUT serialises the JSON object back to KEY=value lines."""
        with patch("app.api.settings.ENV_FILE", self.env):
            resp = client.put("/api/settings/env", json={"GROQ_API_KEY": "1", "FMP_API_KEY": "2"})
        self.assertEqual(resp.status_code, 200)
        written = self.env.read_text(encoding="utf-8")
        self.assertIn("GROQ_API_KEY=1", written)
        self.assertIn("FMP_API_KEY=2", written)

    def test_put_env_preserves_unmanaged_keys_and_comments(self):
        """
        PUT merges into the existing file. A client that only knows about
        provider keys must not be able to drop the KEK: losing MASTER_KEY makes
        every stored API key undecryptable.
        """
        self.env.write_text(
            "# deployment secrets\nMASTER_KEY=kek-value\nGROQ_API_KEY=old\n", encoding="utf-8"
        )
        with patch("app.api.settings.ENV_FILE", self.env):
            resp = client.put("/api/settings/env", json={"GROQ_API_KEY": "new"})
        self.assertEqual(resp.status_code, 200)
        written = self.env.read_text(encoding="utf-8")
        self.assertIn("# deployment secrets", written)
        self.assertIn("MASTER_KEY=kek-value", written)
        self.assertIn("GROQ_API_KEY=new", written)
        self.assertNotIn("GROQ_API_KEY=old", written)

    def test_put_env_removes_key_when_value_is_empty(self):
        """Clearing a provider key in the UI deletes its line."""
        self.env.write_text("GROQ_API_KEY=old\nFMP_API_KEY=keep\n", encoding="utf-8")
        with patch("app.api.settings.ENV_FILE", self.env):
            resp = client.put("/api/settings/env", json={"GROQ_API_KEY": ""})
        self.assertEqual(resp.status_code, 200)
        written = self.env.read_text(encoding="utf-8")
        self.assertNotIn("GROQ_API_KEY", written)
        self.assertIn("FMP_API_KEY=keep", written)

    def test_put_env_rejects_unmanaged_key(self):
        """Only provider keys are writable; the KEK is not settable over HTTP."""
        self.env.write_text("MASTER_KEY=kek-value\n", encoding="utf-8")
        with patch("app.api.settings.ENV_FILE", self.env):
            resp = client.put("/api/settings/env", json={"MASTER_KEY": "attacker-kek"})
        self.assertEqual(resp.status_code, 422)
        self.assertIn("MASTER_KEY=kek-value", self.env.read_text(encoding="utf-8"))

    def test_put_env_rejects_non_object(self):
        """A non-object JSON body is rejected with 422 and writes nothing."""
        with patch("app.api.settings.ENV_FILE", self.env):
            resp = client.put("/api/settings/env", json=["A=1"])
        self.assertEqual(resp.status_code, 422)
        self.assertFalse(self.env.exists())

    def test_put_env_rejects_invalid_key(self):
        """A key that isn't a valid env var name is rejected with 422."""
        with patch("app.api.settings.ENV_FILE", self.env):
            resp = client.put("/api/settings/env", json={"bad key!": "x"})
        self.assertEqual(resp.status_code, 422)
        self.assertFalse(self.env.exists())

    def test_put_env_rejects_newline_in_value(self):
        """A value containing a newline (env-injection) is rejected with 422."""
        with patch("app.api.settings.ENV_FILE", self.env):
            resp = client.put("/api/settings/env", json={"GROQ_API_KEY": "1\nINJECTED=2"})
        self.assertEqual(resp.status_code, 422)
        self.assertFalse(self.env.exists())


if __name__ == "__main__":
    unittest.main()
