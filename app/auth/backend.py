"""
Authentication backend: cookie transport + database strategy.

- **Cookie transport**: HttpOnly, SameSite=Lax, Secure in production. The
  browser sends the cookie automatically; no token handling in JS.
- **DatabaseStrategy**: each session is a row in `accesstoken`. Logout deletes
  the row; "sign out all devices" deletes every row for the user.

Lifetime is 7 days, sliding (refreshed on each request via fastapi-users).
"""

from __future__ import annotations

import os
import uuid
from collections.abc import AsyncGenerator

from fastapi import Depends
from fastapi_users.authentication import (
    AuthenticationBackend,
    CookieTransport,
)
from fastapi_users.authentication.strategy.db import (
    AccessTokenDatabase,
    DatabaseStrategy,
)
from fastapi_users_db_sqlalchemy.access_token import SQLAlchemyAccessTokenDatabase

from app.db.models import AccessToken, User
from app.db.session import AsyncSessionLocal

# 7 days. Sliding window: every authenticated request refreshes the cookie.
SESSION_LIFETIME_SECONDS = 60 * 60 * 24 * 7

# In production set COOKIE_SECURE=true (HTTPS only). Default false so local
# dev over plain HTTP works.
COOKIE_SECURE = os.environ.get("COOKIE_SECURE", "false").lower() == "true"

cookie_transport = CookieTransport(
    cookie_name="hft_session",
    cookie_max_age=SESSION_LIFETIME_SECONDS,
    cookie_httponly=True,
    cookie_secure=COOKIE_SECURE,
    cookie_samesite="lax",
)


# `# type: ignore[type-var]` on the four sites below: our User/AccessToken
# override Mapped[...] columns from the fastapi-users mixins, which makes
# mypy lose track of the UserProtocol/AccessTokenProtocol conformance even
# though it holds at runtime. Localised here, not silenced globally.


async def get_access_token_db() -> AsyncGenerator[AccessTokenDatabase[AccessToken]]:  # type: ignore[type-var]
    """
    Per-request access token DB adapter.
    """
    async with AsyncSessionLocal() as session:
        yield SQLAlchemyAccessTokenDatabase(session, AccessToken)  # type: ignore[type-var]


def get_database_strategy(
    access_token_db: AccessTokenDatabase[AccessToken] = Depends(get_access_token_db),  # type: ignore[type-var]
) -> DatabaseStrategy[User, uuid.UUID, AccessToken]:  # type: ignore[type-var]
    """
    Strategy factory. fastapi-users instantiates one per request.
    """
    return DatabaseStrategy(access_token_db, lifetime_seconds=SESSION_LIFETIME_SECONDS)  # type: ignore[type-var]


auth_backend = AuthenticationBackend(
    name="cookie-db",
    transport=cookie_transport,
    get_strategy=get_database_strategy,
)  # type: ignore[type-var]
