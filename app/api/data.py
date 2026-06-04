"""
Read/browse endpoints the frontend uses to fetch CSV-backed data: raw database
file serving, quarter discovery, the per-quarter aggregated analysis, and stock
price history.

Named `data` (not `database`) to avoid confusion with the `app.database`
data-access package this router reads through.
"""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Request, Response
from fastapi.concurrency import run_in_threadpool

from app.api.common import _QUARTER_RE, _df_to_json_safe_records, _require_quarter
from app.api.paths import DATABASE_DIR, _safe_db_path

router = APIRouter(tags=["data"])


@router.get("/database/{filepath:path}")
def get_database_file(filepath: str) -> Response:
    """Serve a raw CSV/JSON file from the database directory.

    Args:
        filepath: Path relative to the database root.

    Returns:
        The file contents with a CSV or JSON media type.

    Raises:
        HTTPException: 400 on unsafe path, 404 if the file is missing.
    """
    file_path = _safe_db_path(filepath)
    if not file_path.exists():
        raise HTTPException(status_code=404, detail=f"File not found: {filepath}")
    content = file_path.read_text(encoding="utf-8")
    media_type = "text/csv" if filepath.endswith(".csv") else "application/json"
    return Response(content=content, media_type=media_type)


@router.put("/database/{filepath:path}")
async def put_database_file(filepath: str, request: Request) -> dict[str, bool]:
    """Overwrite a database file with the raw request body.

    Args:
        filepath: Path relative to the database root.
        request: The incoming request whose body is written verbatim.

    Returns:
        ``{"ok": True}`` on success.

    Raises:
        HTTPException: 400 on unsafe path.
    """
    file_path = _safe_db_path(filepath)
    body = await request.body()

    def _write() -> None:
        file_path.parent.mkdir(parents=True, exist_ok=True)
        file_path.write_text(body.decode("utf-8"), encoding="utf-8")

    await run_in_threadpool(_write)
    return {"ok": True}


@router.get("/api/database/quarters")
def list_quarters() -> list[str]:
    """List all available quarter folders (YYYYQ[1-4]), sorted chronologically."""
    if not DATABASE_DIR.exists():
        return []
    return sorted(
        d.name for d in DATABASE_DIR.iterdir() if d.is_dir() and _QUARTER_RE.match(d.name)
    )


@router.get("/api/database/quarters/latest")
def latest_quarter() -> dict[str, str | None]:
    """Return the most recent quarter present, or ``{"quarter": None}`` if empty.

    Centralizes "latest quarter" resolution on the backend so the frontend
    doesn't have to sort the list itself.
    """
    if not DATABASE_DIR.exists():
        return {"quarter": None}
    quarters = sorted(
        d.name for d in DATABASE_DIR.iterdir() if d.is_dir() and _QUARTER_RE.match(d.name)
    )
    return {"quarter": quarters[-1] if quarters else None}


@router.get("/api/database/quarters/{quarter}")
def list_quarter_funds(quarter: str) -> list[str]:
    """List the fund file stems present in a given quarter.

    Args:
        quarter: Quarter string in YYYYQ[1-4] format.

    Returns:
        Sorted fund-file stems (filenames without the .csv suffix).

    Raises:
        HTTPException: 422 on invalid quarter, 404 if the quarter is missing.
    """
    sanitized_quarter = _require_quarter(quarter)
    quarter_dir = _safe_db_path(sanitized_quarter)
    if not quarter_dir.exists() or not quarter_dir.is_dir():
        raise HTTPException(status_code=404, detail=f"Quarter not found: {sanitized_quarter}")
    return [f.stem for f in sorted(quarter_dir.glob("*.csv"))]


@router.get("/api/database/quarters/{quarter}/analysis")
def quarter_analysis_endpoint(quarter: str) -> list[dict[str, object]]:
    """Return the per-ticker aggregated quarter analysis.

    Replaces the per-fund CSV fan-out previously done client-side: the frontend
    gets a pre-aggregated leaderboard in a single request instead of fetching
    every fund's CSV.

    Args:
        quarter: Quarter string in YYYYQ[1-4] format.

    Returns:
        JSON-safe per-ticker analysis records (empty list if no data).

    Raises:
        HTTPException: 422 on invalid quarter, 404 if the quarter is missing.
    """
    from app.analysis.stocks import quarter_analysis

    sanitized_quarter = _require_quarter(quarter)
    quarter_dir = _safe_db_path(sanitized_quarter)
    if not quarter_dir.exists() or not quarter_dir.is_dir():
        raise HTTPException(status_code=404, detail=f"Quarter not found: {sanitized_quarter}")
    df = quarter_analysis(sanitized_quarter)
    if df is None or df.empty:
        return []
    return _df_to_json_safe_records(df)


@router.get("/api/stocks/{ticker}/history")
def stock_price_history(ticker: str, range: str = "5y") -> dict[str, object]:
    """Return monthly close prices for a ticker over the requested range.

    Args:
        ticker: Stock ticker (validated/normalised to alphanumeric + ``.-``).
        range: yfinance period string (e.g. "1y", "3y", "5y", "10y", "max").

    Returns:
        ``{"ticker", "range", "points": [{"date", "close"}, ...]}``.

    Raises:
        HTTPException: 400 on invalid ticker or unsupported range.
    """
    sanitized = ticker.strip().upper()
    if not sanitized or len(sanitized) > 16 or not all(c.isalnum() or c in ".-" for c in sanitized):
        raise HTTPException(status_code=400, detail="Invalid ticker")

    allowed_ranges = {"ytd", "1y", "2y", "3y", "5y", "10y", "max"}
    if range not in allowed_ranges:
        raise HTTPException(
            status_code=400, detail=f"Invalid range; allowed: {sorted(allowed_ranges)}"
        )

    from app.stocks.price_fetcher import PriceFetcher

    points = PriceFetcher.get_history(sanitized, range)
    return {"ticker": sanitized, "range": range, "points": points}
