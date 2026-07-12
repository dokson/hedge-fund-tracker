"""
FastAPI dependencies for accessing the current user in route handlers.

Use the strictest one that fits the endpoint:
- `current_optional_user`: routes that work for anonymous + authenticated
  (e.g. public CSV reads).
- `current_active_user`: routes that require login (any tier).
- `current_active_verified_user`: routes that require email verification
  (BYOK, starring, alerts, anything non-trivial). DEFAULT for /api/me/*.
- `current_superuser`: admin-only.

All four are FastAPI dependencies — drop into `Depends()`:

    @app.get("/api/me/api-keys")
    async def list_keys(user: User = Depends(current_active_verified_user)):
        ...
"""

from __future__ import annotations

import uuid

from fastapi import Depends, HTTPException
from fastapi_users import FastAPIUsers  # pyright: ignore[reportMissingImports]

from app.auth.backend import auth_backend
from app.auth.manager import get_user_manager
from app.db.models import User

fastapi_users = FastAPIUsers[User, uuid.UUID](  # type: ignore[type-var]
    get_user_manager,
    [auth_backend],
)

# Optional auth — request may be anonymous.
current_optional_user = fastapi_users.current_user(optional=True, active=True)

# Logged in, account active. Email may not be verified yet.
current_active_user = fastapi_users.current_user(active=True)

# Logged in, account active, email verified. The default for any per-user
# data endpoint.
current_active_verified_user = fastapi_users.current_user(active=True, verified=True)

# Admin only.
current_superuser = fastapi_users.current_user(active=True, superuser=True)


async def require_local_or_superuser(
    user: User | None = Depends(current_optional_user),
) -> User | None:
    """
    Gate for operator-only endpoints (.env settings, admin jobs, database writes).

    Local single-user mode (COOKIE_SECURE unset) keeps them open — the app runs
    as a personal tool on localhost. In a production posture (COOKIE_SECURE set)
    only an authenticated superuser may pass: 401 for anonymous, 403 otherwise.
    """
    from app.auth import backend

    if not backend.COOKIE_SECURE:
        return user
    if user is None:
        raise HTTPException(status_code=401, detail="Authentication required")
    if not user.is_superuser:
        raise HTTPException(status_code=403, detail="Admin privileges required")
    return user
