import unittest

from fastapi import HTTPException

from app.api.paths import _safe_db_path, _safe_frontend_path, _sanitize_path_parts


class TestSanitizePathParts(unittest.TestCase):
    """The basename-based path-injection sanitiser."""

    def test_accepts_simple_relative_path(self):
        """A normal relative path is split into its components."""
        self.assertEqual(_sanitize_path_parts("2024Q1/Fund.csv"), ["2024Q1", "Fund.csv"])

    def test_rejects_empty(self):
        """An empty path is rejected."""
        with self.assertRaises(ValueError):
            _sanitize_path_parts("")

    def test_rejects_traversal_tokens(self):
        """Any '..' or (forward-slash) separator-bearing component is rejected.

        Backslash isn't a path separator on POSIX, so a case like "..\\x" is a
        legal single filename there — not a portable traversal token — and is
        intentionally excluded.
        """
        for bad in ["../etc", "a/../../b", ".."]:
            with self.subTest(value=bad), self.assertRaises(ValueError):
                _sanitize_path_parts(bad)


class TestSafeDbPath(unittest.TestCase):
    """DATABASE_DIR-scoped resolution."""

    def test_traversal_raises_400(self):
        """A traversal attempt raises HTTP 400."""
        with self.assertRaises(HTTPException) as ctx:
            _safe_db_path("../secret")
        self.assertEqual(ctx.exception.status_code, 400)

    def test_safe_path_stays_in_root(self):
        """A clean path resolves inside DATABASE_DIR."""
        from app.api.paths import _DB_ROOT

        resolved = _safe_db_path("stocks.csv")
        self.assertTrue(resolved.is_relative_to(_DB_ROOT))


class TestSafeFrontendPath(unittest.TestCase):
    """FRONTEND_DIST-scoped resolution."""

    def test_traversal_raises_403(self):
        """A traversal attempt raises HTTP 403."""
        with self.assertRaises(HTTPException) as ctx:
            _safe_frontend_path("../../etc/passwd")
        self.assertEqual(ctx.exception.status_code, 403)


if __name__ == "__main__":
    unittest.main()
