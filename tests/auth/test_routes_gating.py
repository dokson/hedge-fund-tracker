"""
Regression tests for the auth router wiring.

We can't easily integration-test "PATCH /users/<other> returns 403" without
spinning up a full DB + auth flow, so we lock in the **shape** of the routes:
- The /users/{id} family (PATCH, DELETE) MUST exist and have an authentication
  dependency. If a future fastapi-users version stops mounting these as
  superuser-only, this test alone won't catch it — but it'll detect the bigger
  regression of "the routes vanished or lost their auth dep entirely".

For the real 403 verification, do a manual smoke test against a running stack:
    curl -X PATCH https://app/users/<some-uuid> -H "Cookie: hft_session=..."
expect: HTTP 403 when authenticated as a non-superuser.
"""

from __future__ import annotations

import unittest


class TestUsersRouterShape(unittest.TestCase):
    """
    Architectural regression tests for /users/{id} routes.
    """

    def test_users_id_routes_have_auth_dependency(self) -> None:
        """
        Each of GET/PATCH/DELETE on /users/{id} must declare at least one
        dependency. The fastapi-users default for these is `current_user(
        active=True, superuser=True)`. Library upgrades that drop the auth
        dep would render the route open — fail the build instead.
        """
        from app.server import app

        protected_methods_seen: set[str] = set()
        for route in app.routes:
            path = getattr(route, "path", None)
            if path != "/users/{id}":
                continue
            methods = getattr(route, "methods", set()) - {"OPTIONS", "HEAD"}
            dependencies = getattr(getattr(route, "dependant", None), "dependencies", [])
            self.assertTrue(
                len(dependencies) > 0,
                f"{methods} /users/{{id}} has no dependencies — auth gating may have regressed",
            )
            protected_methods_seen.update(methods)

        # All three management methods must be registered (regression on missing routes).
        self.assertEqual(
            protected_methods_seen,
            {"GET", "PATCH", "DELETE"},
            "Expected /users/{id} to expose GET, PATCH, DELETE — fastapi-users wiring changed",
        )


if __name__ == "__main__":
    unittest.main()
