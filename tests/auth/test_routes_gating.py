"""
Regression tests for the auth router wiring.

We lock in the **behaviour** of the /users/{id} family rather than its internal
shape: an unauthenticated GET/PATCH/DELETE must be rejected with 401. This is a
stronger guarantee than introspecting `route.dependant.dependencies` (it proves
the gate actually rejects, not merely that a dependency is declared) and it is
immune to FastAPI's internal route representation, which became a router tree in
0.137 — `app.routes` is no longer a flat list of routes to walk.

A 401 (not 404) also proves the route exists: a missing path would fall through
to the SPA catch-all and return 200, so 401 confirms both presence and gating.
"""

from __future__ import annotations

import unittest
from uuid import UUID

try:
    import app.auth  # noqa: F401 — probe import; tests do their own imports lazily.
except ImportError as _e:  # pragma: no cover — optional dep `fastapi_users` missing
    raise unittest.SkipTest(f"app.auth unavailable: {_e}") from None


class TestUsersRouterShape(unittest.TestCase):
    """
    Architectural regression tests for /users/{id} routes.
    """

    def test_users_id_methods_reject_unauthenticated(self) -> None:
        """
        GET/PATCH/DELETE on /users/{id} must reject anonymous callers with 401.

        The fastapi-users default mounts these behind `current_user(active=True,
        superuser=True)`. A library upgrade that dropped the auth dependency would
        leave the route open (200/404 instead of 401) — fail the build instead.
        """
        from starlette.testclient import TestClient

        from app.server import app

        client = TestClient(app)
        # Nil UUID: a valid path param so routing matches and the rejection comes
        # from auth, not from path-parameter validation (which would be 422).
        path = f"/users/{UUID(int=0)}"
        for method in ("GET", "PATCH", "DELETE"):
            with self.subTest(method=method):
                response = client.request(method, path)
                self.assertEqual(
                    response.status_code,
                    401,
                    f"{method} /users/{{id}} returned {response.status_code}, "
                    "expected 401 — auth gating may have regressed",
                )


if __name__ == "__main__":
    unittest.main()
