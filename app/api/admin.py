"""
Database maintenance endpoints: filing fetches (blocking + SSE-streamed),
ticker/CUSIP corrections, NASDAQ ticker-change detection/application, and
quarter-coverage gap reporting.

Business logic lives in service modules (``database.updater``,
``app.database``, ``app.stocks.ticker_changes``); these handlers only
parse/validate input and delegate, lazy-importing heavy deps per the project's
handler convention.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from fastapi import APIRouter, HTTPException, Request
from fastapi.concurrency import run_in_threadpool

from app.api.common import _require_cusip, _require_ticker
from app.api.sse import _make_sse_stream

if TYPE_CHECKING:
    from fastapi.responses import StreamingResponse

router = APIRouter(tags=["admin"])


@router.post("/api/database/fetch")
async def database_fetch(request: Request) -> dict[str, bool]:
    """
    Run the full 13F fetch/report pipeline for all tracked funds.
    """
    body = await request.json()
    fetch_type = body.get("type", "all")
    if fetch_type != "all":
        raise HTTPException(status_code=422, detail=f"Unknown fetch type: {fetch_type}")

    from database.updater import run_all_funds_report

    await run_in_threadpool(run_all_funds_report)
    return {"ok": True}


@router.post("/api/update-all")
def update_all() -> dict[str, str]:
    """
    Regenerate all 13F reports (blocking; runs in a threadpool worker).
    """
    from database.updater import run_all_funds_report

    run_all_funds_report()
    return {"message": "All 13F reports generated successfully"}


@router.post("/api/update-all/stream")
async def update_all_stream() -> StreamingResponse:
    """
    Regenerate all 13F reports, streaming progress over SSE.
    """
    from database.updater import run_all_funds_report

    return _make_sse_stream(
        lambda: (run_all_funds_report(), "All 13F reports generated successfully")[1]
    )


@router.post("/api/fetch-nq")
def fetch_nq() -> dict[str, str]:
    """
    Fetch the latest non-quarterly (13D/G, Form 4) filings (blocking; threadpool).
    """
    from database.updater import run_fetch_nq_filings

    run_fetch_nq_filings()
    return {"message": "Non-quarterly filings fetched successfully"}


@router.post("/api/fetch-nq/stream")
async def fetch_nq_stream() -> StreamingResponse:
    """
    Fetch the latest non-quarterly filings, streaming progress over SSE.
    """
    from database.updater import run_fetch_nq_filings

    return _make_sse_stream(
        lambda: (run_fetch_nq_filings(), "Non-quarterly filings fetched successfully")[1]
    )


@router.post("/api/update-ticker")
async def update_ticker_endpoint(request: Request) -> dict[str, str]:
    """
    Rename a ticker across stocks.csv and all filings.
    """
    from app.database import update_ticker

    body = await request.json()
    old_ticker = _require_ticker(body.get("old_ticker", "").strip())
    new_ticker = _require_ticker(body.get("new_ticker", "").strip())
    new_company = body.get("new_company", "").strip() or None
    await run_in_threadpool(update_ticker, old_ticker, new_ticker, new_company=new_company)
    return {"message": f"Ticker updated: {old_ticker} → {new_ticker}"}


@router.post("/api/update-cusip-ticker")
async def update_cusip_ticker_endpoint(request: Request) -> dict[str, str]:
    """
    Rename the ticker for a single CUSIP across the database.
    """
    from app.database import update_ticker_for_cusip

    body = await request.json()
    cusip = _require_cusip(body.get("cusip", "").strip())
    new_ticker = _require_ticker(body.get("new_ticker", "").strip())
    new_company = body.get("new_company", "").strip() or None
    await run_in_threadpool(update_ticker_for_cusip, cusip, new_ticker, new_company=new_company)
    return {"message": f"CUSIP {cusip} ticker updated to {new_ticker}"}


@router.get("/api/detect-ticker-changes")
def detect_ticker_changes_endpoint() -> dict:
    """
    Fetches recent symbol changes from NASDAQ and returns those applicable to stocks.csv.
    """
    from app.stocks.ticker_changes import detect_applicable_ticker_changes

    return detect_applicable_ticker_changes()


@router.post("/api/apply-ticker-changes")
def apply_ticker_changes_endpoint() -> dict:
    """
    Detects and applies all applicable ticker changes from NASDAQ across the entire database.
    """
    from app.stocks.ticker_changes import apply_ticker_changes

    return apply_ticker_changes()


@router.post("/api/funds-missing-quarters")
def funds_missing_quarters_endpoint() -> dict[str, object]:
    """
    Lists funds that are missing data for one or more available quarters.
    """
    from app.database import get_funds_missing_quarters

    missing = get_funds_missing_quarters()
    if not missing:
        message = "All tracked funds have complete quarter coverage."
    else:
        lines = [f"{fund}: missing {', '.join(quarters)}" for fund, quarters in missing.items()]
        message = f"{len(missing)} fund(s) with gaps:\n" + "\n".join(lines)
    return {"missing": missing, "message": message}
