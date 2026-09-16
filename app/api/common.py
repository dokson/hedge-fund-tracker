"""
Shared API infrastructure: the rate limiter, request validation, and JSON-safe
serialization.

Lives in its own module so routers (``app/api/*``) can import these without an
import cycle back to ``app.server`` (which includes those routers).
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import limits
from fastapi import HTTPException, Request
from slowapi import Limiter
from slowapi.util import get_remote_address

from app.patterns import CUSIP_RE, QUARTER_RE, TICKER_RE

if TYPE_CHECKING:
    import pandas as pd

# Rate limiter, keyed by client IP for now (pre-auth). After we add user
# accounts, switch the key_func to read the authenticated user_id from
# request.state. Created here and registered on the app in app.server.
limiter = Limiter(key_func=get_remote_address, default_limits=["120/minute"])

# Credential endpoints get their own, much tighter bucket: at the site-wide
# default a single client could try 120 passwords — or trigger 120 password
# reset emails to a third party — every minute.
AUTH_RATE_LIMIT = limits.parse("10/minute")
_AUTH_BUCKET = "auth"


def _auth_rate_limit_key(request: Request) -> str:
    """
    Bucket credential attempts per client IP, shared across every auth route so
    rotating between login and forgot-password doesn't multiply the allowance.
    """
    return f"{_AUTH_BUCKET}:{get_remote_address(request)}"


def reset_auth_rate_limit(client_ip: str) -> None:
    """
    Clear one client's credential bucket.
    """
    limiter.limiter.clear(AUTH_RATE_LIMIT, f"{_AUTH_BUCKET}:{client_ip}")


async def enforce_auth_rate_limit(request: Request) -> None:
    """
    Dependency for the fastapi-users routers, which are mounted wholesale and so
    can't carry a @limiter.limit decorator on individual endpoints.
    """
    if not limiter.limiter.hit(AUTH_RATE_LIMIT, _auth_rate_limit_key(request)):
        raise HTTPException(
            status_code=429,
            detail="Too many authentication attempts. Try again in a minute.",
            headers={"Retry-After": "60"},
        )


def _require_quarter(quarter: str | None) -> str:
    """
    Validate a quarter string is YYYYQ[1-4]; raise 422 otherwise.
    """
    if not quarter or not QUARTER_RE.match(quarter):
        raise HTTPException(status_code=422, detail="quarter must be in YYYYQ[1-4] format")
    return quarter


def _require_ticker(ticker: str | None) -> str:
    """
    Validate and normalise a ticker to upper-case; raise 422 otherwise.
    """
    if not ticker or not TICKER_RE.match(ticker.upper()):
        raise HTTPException(status_code=422, detail="Invalid ticker format")
    return ticker.upper()


def _require_cusip(cusip: str | None) -> str:
    """
    Validate and normalise a 9-char CUSIP to upper-case; raise 422 otherwise.
    """
    if not cusip or not CUSIP_RE.match(cusip.upper()):
        raise HTTPException(status_code=422, detail="CUSIP must be 9 alphanumeric characters")
    return cusip.upper()


def _df_to_json_safe_records(df: pd.DataFrame) -> list[dict[str, object]]:
    """
    Convert a pandas DataFrame to a list of records, replacing values that are not
    valid in standard JSON (±Infinity, NaN) with None so the browser's JSON.parse accepts them.

    Args:
        df: Input DataFrame; arbitrary dtypes are supported (numeric, object, datetime).

    Returns:
        Records ready for JSON serialization, with ±Infinity and NaN replaced by None.
    """
    import numpy as np

    cleaned = df.replace([np.inf, -np.inf], np.nan).astype(object)
    return cleaned.where(cleaned.notna(), None).to_dict(orient="records")  # type: ignore[return-value]
