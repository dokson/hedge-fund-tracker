"""
Shared API infrastructure: the rate limiter, request validation, and JSON-safe
serialization.

Lives in its own module so routers (``app/api/*``) can import these without an
import cycle back to ``app.server`` (which includes those routers).
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from fastapi import HTTPException
from slowapi import Limiter
from slowapi.util import get_remote_address

from app.patterns import CUSIP_RE, QUARTER_RE, TICKER_RE

if TYPE_CHECKING:
    import pandas as pd

# Rate limiter, keyed by client IP for now (pre-auth). After we add user
# accounts, switch the key_func to read the authenticated user_id from
# request.state. Created here and registered on the app in app.server.
limiter = Limiter(key_func=get_remote_address, default_limits=["120/minute"])


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
