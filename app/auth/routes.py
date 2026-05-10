"""
Wires the fastapi-users routers into the FastAPI app.

Routes mounted (under /auth and /users):
- POST /auth/register
- POST /auth/cookie-db/login
- POST /auth/cookie-db/logout
- POST /auth/forgot-password
- POST /auth/reset-password
- POST /auth/request-verify-token
- POST /auth/verify
- GET  /users/me
- PATCH /users/me
- GET  /users/{id}                (superuser only)
- PATCH /users/{id}               (superuser only)
- DELETE /users/{id}              (superuser only)

Per the design doc: email verification is HARD-required for any non-public
data endpoint. We don't gate the routes above — fastapi-users does that for
us by checking `is_verified` on `current_active_verified_user`.
"""

from __future__ import annotations

from fastapi import FastAPI

from app.auth.backend import auth_backend
from app.auth.dependencies import fastapi_users
from app.auth.schemas import UserCreate, UserRead, UserUpdate


def include_routers_for_auth(app: FastAPI) -> None:
    """
    Mount all auth-related routers on the app. Call this once at startup.
    """
    app.include_router(
        fastapi_users.get_auth_router(auth_backend),
        prefix="/auth/cookie-db",
        tags=["auth"],
    )
    app.include_router(
        fastapi_users.get_register_router(UserRead, UserCreate),
        prefix="/auth",
        tags=["auth"],
    )
    app.include_router(
        fastapi_users.get_reset_password_router(),
        prefix="/auth",
        tags=["auth"],
    )
    app.include_router(
        fastapi_users.get_verify_router(UserRead),
        prefix="/auth",
        tags=["auth"],
    )
    # `get_users_router` mounts:
    #   GET /users/me, PATCH /users/me  → current_active_user (any logged-in)
    #   GET /users/{id}, PATCH /users/{id}, DELETE /users/{id}  → SUPERUSER ONLY
    # The /users/{id} routes are NOT a self-service endpoint for users to edit
    # themselves — they're admin endpoints. Regression-test: when bumping
    # fastapi-users, smoke-check that PATCH /users/<other-id> returns 403 for
    # a non-superuser, NOT 200. See tests/auth/test_routes_gating.py.
    app.include_router(
        fastapi_users.get_users_router(UserRead, UserUpdate),
        prefix="/users",
        tags=["users"],
    )
