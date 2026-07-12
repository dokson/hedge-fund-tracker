import shutil
import tempfile
import unittest
import uuid
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

from fastapi.testclient import TestClient

from app.auth.dependencies import current_optional_user
from app.server import app

client = TestClient(app)


def _user(*, superuser: bool = False, verified: bool = True) -> MagicMock:
    """
    Build a stand-in authenticated user for dependency overrides.
    """
    user = MagicMock()
    user.id = uuid.uuid4()
    user.is_superuser = superuser
    user.is_verified = verified
    user.is_active = True
    return user


class _IsolatedTargetsMixin(unittest.TestCase):
    """
    Redirect every mutable target (.env, database writes, admin jobs) to temp
    or mock objects, so no request in this file can touch real files even when
    a gating assertion fails.
    """

    def setUp(self):
        """Patch the real file targets away before every test."""
        self._tmp = Path(tempfile.mkdtemp(prefix="hft_gating_"))
        self.addCleanup(shutil.rmtree, self._tmp, ignore_errors=True)

        self.env_file = self._tmp / ".env"
        for target, replacement in (
            ("app.api.settings.ENV_FILE", self.env_file),
            ("app.api.data._safe_db_path", lambda p: self._tmp / "db" / Path(p).name),
        ):
            patcher = patch(target, replacement)
            patcher.start()
            self.addCleanup(patcher.stop)

    def override_user(self, user):
        """Make every request resolve `current_optional_user` to `user`."""
        app.dependency_overrides[current_optional_user] = lambda: user
        self.addCleanup(app.dependency_overrides.pop, current_optional_user, None)


class TestOperatorGatingProduction(_IsolatedTargetsMixin):
    """In production posture (COOKIE_SECURE), operator endpoints require a superuser."""

    def setUp(self):
        """Force the production posture for every request in this class."""
        super().setUp()
        patcher = patch("app.auth.backend.COOKIE_SECURE", True)
        patcher.start()
        self.addCleanup(patcher.stop)

    def test_get_settings_env_anonymous_401(self):
        """Anonymous callers must not read provider keys in production."""
        resp = client.get("/api/settings/env")
        self.assertEqual(resp.status_code, 401)

    def test_put_settings_env_anonymous_401(self):
        """Anonymous callers must not rewrite .env in production."""
        resp = client.put("/api/settings/env", json={"A": "1"})
        self.assertEqual(resp.status_code, 401)
        self.assertFalse(self.env_file.exists())

    def test_put_database_file_anonymous_401(self):
        """Anonymous callers must not overwrite database files in production."""
        resp = client.put("/database/stocks.csv", content=b"CUSIP,Ticker,Company\n")
        self.assertEqual(resp.status_code, 401)
        self.assertFalse((self._tmp / "db" / "stocks.csv").exists())

    def test_admin_endpoint_anonymous_401(self):
        """Anonymous callers must not reach admin handlers in production."""
        with patch("app.database.get_funds_missing_quarters") as job:
            resp = client.post("/api/funds-missing-quarters")
        self.assertEqual(resp.status_code, 401)
        job.assert_not_called()

    def test_non_superuser_403(self):
        """A logged-in non-admin gets 403, not access."""
        self.override_user(_user(superuser=False))
        resp = client.get("/api/settings/env")
        self.assertEqual(resp.status_code, 403)

    def test_superuser_allowed(self):
        """A superuser passes the gate and reaches the handler."""
        self.override_user(_user(superuser=True))
        resp = client.get("/api/settings/env")
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.json(), {})


class TestOperatorGatingLocal(_IsolatedTargetsMixin):
    """Local single-user mode (COOKIE_SECURE unset) keeps operator endpoints open."""

    def test_get_settings_env_anonymous_ok(self):
        """The local tool works without any login."""
        resp = client.get("/api/settings/env")
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.json(), {})


class TestAiKeyResolution(_IsolatedTargetsMixin):
    """/api/ai/* resolves BYOK keys per posture and caller identity."""

    def _post_promise_score(self):
        """Fire a minimal valid promise-score request with the agent mocked out."""
        with (
            patch("app.api.ai._build_ai_client") as mock_build,
            patch("app.ai.agent.AnalystAgent") as mock_agent_cls,
        ):
            import pandas as pd

            mock_agent_cls.return_value.generate_scored_list.return_value = pd.DataFrame()
            resp = client.post(
                "/api/ai/promise-score",
                json={"quarter": "2024Q1", "provider_id": "groq", "model_id": "m"},
            )
        return resp, mock_build

    def test_production_anonymous_401(self):
        """Anonymous AI calls are rejected in production (no operator-key burn)."""
        with patch("app.auth.backend.COOKIE_SECURE", True):
            resp, mock_build = self._post_promise_score()
        self.assertEqual(resp.status_code, 401)
        mock_build.assert_not_called()

    def test_production_user_without_key_400(self):
        """In production a logged-in user without a stored key gets a helpful 400."""
        from app.auth.api_keys import NoSuchApiKeyError

        self.override_user(_user())
        with (
            patch("app.auth.backend.COOKIE_SECURE", True),
            patch("app.auth.api_keys.get_for_use", AsyncMock(side_effect=NoSuchApiKeyError("x"))),
        ):
            resp, mock_build = self._post_promise_score()
        self.assertEqual(resp.status_code, 400)
        self.assertIn("API key", resp.json()["detail"])
        mock_build.assert_not_called()

    def test_stored_key_is_used(self):
        """An authenticated user's stored key is passed to the client builder."""
        self.override_user(_user())
        with patch("app.auth.api_keys.get_for_use", AsyncMock(return_value="sk-stored")):
            resp, mock_build = self._post_promise_score()
        self.assertEqual(resp.status_code, 200)
        mock_build.assert_called_once_with("groq", "sk-stored", "m")

    def test_local_anonymous_falls_back_to_env(self):
        """Anonymous local calls keep the env-var key fallback (api_key=None)."""
        resp, mock_build = self._post_promise_score()
        self.assertEqual(resp.status_code, 200)
        mock_build.assert_called_once_with("groq", None, "m")

    def test_local_user_without_key_falls_back_to_env(self):
        """A logged-in local user without a stored key still gets the env fallback."""
        from app.auth.api_keys import NoSuchApiKeyError

        self.override_user(_user())
        with patch("app.auth.api_keys.get_for_use", AsyncMock(side_effect=NoSuchApiKeyError("x"))):
            resp, mock_build = self._post_promise_score()
        self.assertEqual(resp.status_code, 200)
        mock_build.assert_called_once_with("groq", None, "m")


class TestRateLimitMiddleware(unittest.TestCase):
    """The default rate limits must actually be enforced by the middleware."""

    def test_slowapi_middleware_registered(self):
        """SlowAPIMiddleware is installed so `default_limits` applies to all routes."""
        from slowapi.middleware import SlowAPIMiddleware

        self.assertTrue(any(m.cls is SlowAPIMiddleware for m in app.user_middleware))


if __name__ == "__main__":
    unittest.main()
