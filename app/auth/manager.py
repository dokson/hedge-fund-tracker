"""
UserManager: business logic around user lifecycle (create / verify / login /
forgot-password). fastapi-users dispatches to these hooks at the right moments;
we use them to send emails and write audit log entries.
"""

from __future__ import annotations

import asyncio
import os
import uuid
from collections.abc import AsyncGenerator

from fastapi import Depends, Request
from fastapi_users import BaseUserManager, UUIDIDMixin
from fastapi_users.db import SQLAlchemyUserDatabase

from app.auth import api_keys as api_keys_svc
from app.auth.email import send_password_reset_email, send_verification_email
from app.db.models import User
from app.db.session import AsyncSessionLocal

# Secrets used by fastapi-users to sign verification + reset tokens.
# Different per purpose so a leaked verification token can't be replayed as a
# password-reset token. Env vars in production.
RESET_PASSWORD_TOKEN_SECRET = os.environ.get(
    "RESET_PASSWORD_TOKEN_SECRET", "dev-only-change-in-production-reset"
)
VERIFICATION_TOKEN_SECRET = os.environ.get(
    "VERIFICATION_TOKEN_SECRET", "dev-only-change-in-production-verify"
)


class UserManager(UUIDIDMixin, BaseUserManager[User, uuid.UUID]):  # type: ignore[type-var]
    """
    Hooks fired by fastapi-users at the right lifecycle moments.

    Each hook also writes an audit_log entry (TODO: wire after the
    AuditLog helper module lands — keep TODOs in code, not commits).

    Token lifetimes are explicit (not relying on the library default) so a
    future fastapi-users version can't silently extend our threat window.
    """

    reset_password_token_secret = RESET_PASSWORD_TOKEN_SECRET
    verification_token_secret = VERIFICATION_TOKEN_SECRET
    # 1 hour: enough for a user to read the email and click; short enough that a
    # leaked link from a forwarded inbox is rarely useful.
    reset_password_token_lifetime_seconds = 3600
    # 24 hours: longer because users may sign up and verify the next day.
    verification_token_lifetime_seconds = 86400

    async def on_after_register(self, user: User, request: Request | None = None) -> None:
        """
        Right after signup. Two side effects:

        1. Provision the user's encryption key (DEK) so BYOK works as soon as
           they verify their email and start adding API keys. Done synchronously
           to surface KEK misconfiguration early — better fail signup loudly than
           hand the user a broken account.
        2. Email verification: fastapi-users handles the request via
           `request_verify_token`; we don't need to send it here unless we want
           a custom flow.
        """
        async with AsyncSessionLocal() as session:
            await api_keys_svc.ensure_user_secret(session, user)
            await session.commit()

    async def on_after_request_verify(
        self, user: User, token: str, request: Request | None = None
    ) -> None:
        """
        Fired when fastapi-users generates a verification token. Email send is
        fire-and-forget (`asyncio.create_task`) so the HTTP response time is
        constant whether the SMTP/Resend call takes 50 ms or 5 s — a timing
        side-channel could otherwise be used for account enumeration.
        """
        asyncio.create_task(send_verification_email(user.email, token))

    async def on_after_verify(self, user: User, request: Request | None = None) -> None:
        """
        After the user clicks the verification link. Audit-log here.
        """

    async def on_after_login(
        self,
        user: User,
        request: Request | None = None,
        response=None,
    ) -> None:
        """
        Successful login. Audit-log here.
        """

    async def on_after_forgot_password(
        self, user: User, token: str, request: Request | None = None
    ) -> None:
        """
        Fired only when the email matched a real user. We dispatch the email
        as a background task so the response time of /auth/forgot-password
        looks the same to an attacker regardless of whether the email exists,
        making account enumeration via timing impractical.
        """
        asyncio.create_task(send_password_reset_email(user.email, token))

    async def on_after_reset_password(self, user: User, request: Request | None = None) -> None:
        """
        Password was changed via the reset flow. Audit-log here.
        """


async def get_user_db() -> AsyncGenerator[SQLAlchemyUserDatabase]:
    """
    fastapi-users database adapter. We open a fresh session per request rather
    than reusing app.db.session.get_session because fastapi-users wires this
    at router-include time, before our app's dependency machinery is known.
    """
    async with AsyncSessionLocal() as session:
        yield SQLAlchemyUserDatabase(session, User)


async def get_user_manager(
    user_db: SQLAlchemyUserDatabase = Depends(get_user_db),
) -> AsyncGenerator[UserManager]:
    """
    Factory for UserManager — required by fastapi-users.
    """
    yield UserManager(user_db)
