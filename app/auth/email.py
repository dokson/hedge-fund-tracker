"""
Transactional email sender.

v1 ships a stub that logs the email to stdout — sufficient for local dev and
to verify the auth flow without burning Resend quota. When `RESEND_API_KEY`
is set, switches to actually sending via the Resend HTTP API.

Add a real provider integration (Resend, Postmark, AWS SES, ...) when ready.
This module is the single seam that has to change.
"""

from __future__ import annotations

import logging
import os
from typing import Final

import requests

logger = logging.getLogger(__name__)

RESEND_API_KEY: Final = os.environ.get("RESEND_API_KEY", "")
FROM_EMAIL: Final = os.environ.get("FROM_EMAIL", "no-reply@hedge-fund-tracker.local")
APP_BASE_URL: Final = os.environ.get("APP_BASE_URL", "http://localhost:8000")

# Resend HTTP API endpoint. https://resend.com/docs/api-reference/emails/send-email
_RESEND_URL: Final = "https://api.resend.com/emails"
_REQUEST_TIMEOUT: Final = 10


async def _send(to: str, subject: str, html: str) -> None:
    """
    Dispatch one email. Logs to stdout if RESEND_API_KEY is unset (dev mode);
    POSTs to Resend otherwise. Failures are logged, not raised — a transient
    email outage shouldn't block signup.
    """
    if not RESEND_API_KEY:
        logger.info("[email:dev-stub] to=%s subject=%r body=%r", to, subject, html)
        return

    try:
        response = requests.post(
            _RESEND_URL,
            json={"from": FROM_EMAIL, "to": [to], "subject": subject, "html": html},
            headers={"Authorization": f"Bearer {RESEND_API_KEY}"},
            timeout=_REQUEST_TIMEOUT,
        )
        response.raise_for_status()
    except requests.RequestException:
        logger.exception("Failed to send email to %s (subject=%r)", to, subject)


async def send_verification_email(to: str, token: str) -> None:
    """
    Send the email-verification link. The token is the fastapi-users
    JWT-signed verification token.
    """
    link = f"{APP_BASE_URL}/auth/verify?token={token}"
    html = f"""
    <p>Welcome to Hedge Fund Tracker.</p>
    <p>Please confirm your email by clicking the link below — it expires in 1 hour.</p>
    <p><a href="{link}">Verify my email</a></p>
    <p>If you didn't sign up, you can ignore this message.</p>
    """
    await _send(to, "Verify your email", html)


async def send_password_reset_email(to: str, token: str) -> None:
    """
    Send the password-reset link.
    """
    link = f"{APP_BASE_URL}/auth/reset-password?token={token}"
    html = f"""
    <p>You asked to reset your Hedge Fund Tracker password.</p>
    <p>The link below expires in 1 hour:</p>
    <p><a href="{link}">Reset my password</a></p>
    <p>If you didn't request this, you can safely ignore this email.</p>
    """
    await _send(to, "Reset your password", html)
