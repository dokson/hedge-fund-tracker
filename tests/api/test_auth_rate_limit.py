"""
Credential endpoints need a bucket far tighter than the site-wide default:
the default allows 120 password guesses — or 120 reset emails — per minute.

The routing assertions deliberately pre-exhaust the bucket: the guard runs
before the handler, so a throttled route answers 429 without ever reaching the
database these endpoints would otherwise need.
"""

import asyncio
import contextlib
import unittest
from unittest.mock import MagicMock

from fastapi import HTTPException
from fastapi.testclient import TestClient

from app.api.common import (
    AUTH_RATE_LIMIT,
    enforce_auth_rate_limit,
    limiter,
    reset_auth_rate_limit,
)
from app.server import app

client = TestClient(app)

# The host TestClient reports, i.e. the key its requests land under.
_TEST_CLIENT_IP = "testclient"


def _request(client_ip: str) -> MagicMock:
    """
    Build the minimal Request stand-in slowapi's key function reads.
    """
    request = MagicMock()
    request.client.host = client_ip
    request.headers = {}
    return request


def _hit(client_ip: str) -> None:
    """
    Run the dependency once for the given client.
    """
    asyncio.run(enforce_auth_rate_limit(_request(client_ip)))


class TestAuthRateLimit(unittest.TestCase):
    """
    The stricter limit applies per client and is releasable.
    """

    def setUp(self):
        """Start each test with an empty bucket."""
        limiter.reset()
        self.addCleanup(limiter.reset)

    def test_limit_is_stricter_than_the_site_default(self):
        """
        A brute-force bucket is only meaningful well below the 120/minute the
        rest of the API gets.
        """
        self.assertLessEqual(AUTH_RATE_LIMIT.amount, 10)

    def test_allows_traffic_up_to_the_limit_then_rejects(self):
        """
        Repeated attempts from one client are refused once the bucket empties.
        """
        for _ in range(AUTH_RATE_LIMIT.amount):
            _hit("1.2.3.4")

        with self.assertRaises(HTTPException) as caught:
            _hit("1.2.3.4")
        self.assertEqual(caught.exception.status_code, 429)

    def test_buckets_are_per_client(self):
        """
        One attacker must not lock every other user out of logging in.
        """
        for _ in range(AUTH_RATE_LIMIT.amount + 1):
            with contextlib.suppress(HTTPException):
                _hit("1.2.3.4")

        _hit("5.6.7.8")  # must not raise

    def test_reset_clears_one_client_bucket(self):
        """
        The reset helper releases a single client without flushing the rest.
        """
        for _ in range(AUTH_RATE_LIMIT.amount):
            _hit("1.2.3.4")
            _hit("5.6.7.8")
        reset_auth_rate_limit("1.2.3.4")

        _hit("1.2.3.4")  # must not raise
        with self.assertRaises(HTTPException):
            _hit("5.6.7.8")


class TestAuthRoutersAreThrottled(unittest.TestCase):
    """
    The guard is useless unless every credential router actually carries it.
    """

    def setUp(self):
        """Empty the credential bucket for the TestClient's key."""
        limiter.reset()
        self.addCleanup(limiter.reset)
        for _ in range(AUTH_RATE_LIMIT.amount):
            _hit(_TEST_CLIENT_IP)

    def test_login_is_throttled(self):
        """Password guessing shares the bucket."""
        response = client.post(
            "/auth/cookie-db/login", data={"username": "a@b.co", "password": "x"}
        )
        self.assertEqual(response.status_code, 429)

    def test_register_is_throttled(self):
        """Mass account creation shares the bucket."""
        response = client.post("/auth/register", json={"email": "a@b.co", "password": "x"})
        self.assertEqual(response.status_code, 429)

    def test_forgot_password_is_throttled(self):
        """Mail bombing a third party shares the bucket."""
        response = client.post("/auth/forgot-password", json={"email": "victim@example.com"})
        self.assertEqual(response.status_code, 429)

    def test_request_verify_token_is_throttled(self):
        """The verification resend shares the bucket."""
        response = client.post("/auth/request-verify-token", json={"email": "a@b.co"})
        self.assertEqual(response.status_code, 429)

    def test_unrelated_endpoints_keep_the_default_allowance(self):
        """
        Exhausting the credential bucket must not lock the caller out of the app.
        """
        self.assertEqual(client.get("/health").status_code, 200)


if __name__ == "__main__":
    unittest.main()
