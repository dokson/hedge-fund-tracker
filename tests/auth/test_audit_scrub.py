"""
Tests for the audit-log metadata scrubber. The scrubber is a defence-in-depth:
even if a future caller passes secret values into `metadata`, they won't land
in the queryable JSONB column.
"""

from __future__ import annotations

import unittest

from app.auth.audit import _scrub_metadata


class TestScrubMetadata(unittest.TestCase):
    """
    The scrubber drops keys that match the secrets-name regex.
    """

    def test_drops_obvious_secret_keys(self) -> None:
        """
        Common shapes of accidental secret keys are removed.
        """
        result = _scrub_metadata(
            {
                "ip": "1.2.3.4",
                "password": "hunter2",
                "api_key": "sk-test",
                "apikey": "sk-test",
                "PASSWORD": "hunter2",
                "user_token": "tok",
                "auth_secret": "x",
            }
        )
        self.assertEqual(result, {"ip": "1.2.3.4"})

    def test_preserves_innocuous_keys_with_substring_collisions(self) -> None:
        """
        Words that look like secrets but aren't (last4, tokenizer) survive.
        """
        result = _scrub_metadata({"last4": "QXY7", "tokenizer": "fast"})
        self.assertEqual(result, {"last4": "QXY7", "tokenizer": "fast"})

    def test_empty_input_returns_none(self) -> None:
        """
        Empty / None inputs round-trip to None — JSONB column stores NULL.
        """
        self.assertIsNone(_scrub_metadata(None))
        self.assertIsNone(_scrub_metadata({}))

    def test_only_secret_keys_returns_none(self) -> None:
        """
        If every key is dropped, return None rather than `{}`. NULL is the
        honest representation of "no metadata after scrub".
        """
        self.assertIsNone(_scrub_metadata({"password": "x"}))


if __name__ == "__main__":
    unittest.main()
