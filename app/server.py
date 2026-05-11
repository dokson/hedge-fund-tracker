import asyncio
import contextvars
import json
import os
import queue
import re
import sys
import threading
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    import pandas as pd

# Fix terminal width for output streamed to the web UI
os.environ.setdefault("COLUMNS", "80")

from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, Request, Response
from fastapi.exceptions import HTTPException as StarletteHTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse, StreamingResponse
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.util import get_remote_address
from starlette.middleware.base import BaseHTTPMiddleware

from app.api.api_keys import router as api_keys_router
from app.api.me import router as me_router
from app.api.starred import router as starred_router
from app.auth import include_routers_for_auth
from app.db.models import User
from app.db.session import AsyncSessionLocal

DATABASE_DIR = Path(__file__).parent.parent / "database"
FRONTEND_DIST = Path(__file__).parent / "frontend" / "dist"
ENV_FILE = Path(__file__).parent.parent / ".env"


@asynccontextmanager
async def _lifespan(app: FastAPI):
    """
    Validate critical secrets eagerly at startup so a misconfigured deployment
    crashes the worker immediately — rather than serving for hours and then
    503-ing the first user who tries BYOK signup.
    """
    from app.security.envelope import _kek

    # Touch the KEK loader; raises EncryptionConfigError if MASTER_KEY is unset
    # or malformed. Fails the worker boot, surfaces the misconfig in `docker logs`.
    _kek()
    yield
    # Shutdown: no cleanup yet.


app = FastAPI(title="Hedge Fund Tracker", lifespan=_lifespan)

# ── CORS allowlist ────────────────────────────────────────────────────────────
# Read from env var (comma-separated). Defaults to localhost dev origins so a
# fresh checkout works without configuration. In production, set ALLOWED_ORIGINS
# explicitly to your domain(s); never leave wildcards in a public deployment.
_default_origins = "http://localhost:5173,http://localhost:8000,http://127.0.0.1:8000"
ALLOWED_ORIGINS = [
    o.strip() for o in os.environ.get("ALLOWED_ORIGINS", _default_origins).split(",") if o.strip()
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
    allow_headers=["*"],
)


# ── Security headers ──────────────────────────────────────────────────────────
class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    """
    Adds defensive HTTP headers to every response. CSP is intentionally lax in
    style/script directives because Vite injects inline assets at build time;
    tightening it requires nonces or hashes per build, deferred for later.
    """

    async def dispatch(self, request: Request, call_next):
        response = await call_next(request)
        response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        response.headers["Permissions-Policy"] = "geolocation=(), microphone=(), camera=()"
        # CSP report-only initially: logs violations without blocking, so we can
        # tune the policy against the real React bundle before enforcing it.
        response.headers["Content-Security-Policy-Report-Only"] = (
            "default-src 'self'; "
            "script-src 'self' 'unsafe-inline'; "
            "style-src 'self' 'unsafe-inline'; "
            "img-src 'self' data: https:; "
            "font-src 'self' data:; "
            "connect-src 'self'; "
            "frame-ancestors 'none'; "
            "base-uri 'self'"
        )
        return response


app.add_middleware(SecurityHeadersMiddleware)


# ── Rate limiting ─────────────────────────────────────────────────────────────
# Keyed by client IP for now (pre-auth). After we add user accounts, switch the
# key_func to read the authenticated user_id from request.state.
limiter = Limiter(key_func=get_remote_address, default_limits=["120/minute"])
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)  # type: ignore[arg-type]


# ── Auth + per-user routes ────────────────────────────────────────────────────
include_routers_for_auth(app)
app.include_router(me_router)
app.include_router(api_keys_router)
app.include_router(starred_router)


@app.get("/health")
async def health_check():
    """
    Health check endpoint for Docker and load balancers.
    """
    return {"status": "healthy"}


# ── Input validation helpers ───────────────────────────────────────────────────

_DB_ROOT = DATABASE_DIR.resolve()
_FRONTEND_ROOT = FRONTEND_DIST.resolve()
_QUARTER_RE = re.compile(r"^\d{4}Q[1-4]$")
_TICKER_RE = re.compile(r"^[A-Z0-9.\-]{1,10}$")
_CUSIP_RE = re.compile(r"^[A-Z0-9]{9}$")


def _sanitize_path_parts(filepath: str) -> list[str]:
    """
    Split filepath into parts and validate each with os.path.basename().

    os.path.basename() is the CodeQL-recognised sanitizer for py/path-injection:
    if basename(part) != part, the part contained a directory separator and is
    rejected.  All parts are then used to reconstruct the path from a safe root,
    so no user-controlled string ever appears directly in a joinpath() call.
    """
    if not filepath:
        raise ValueError("Empty path")
    parts = Path(filepath).parts
    safe: list[str] = []
    for part in parts:
        clean = Path(part).name
        # Reject if basename changed (contained separator) or is a traversal token
        if not clean or clean in (".", "..") or clean != part:
            raise ValueError(f"Unsafe path component: {part!r}")
        # Reject drive letters, colons, and null bytes
        if ":" in clean or "\x00" in clean:
            raise ValueError(f"Unsafe path component: {part!r}")
        safe.append(clean)
    return safe


def _safe_db_path(filepath: str) -> Path:
    """
    Resolve filepath inside DATABASE_DIR; raise 400 on path traversal.

    Each component is validated via os.path.basename() before being joined to
    the database root, breaking the taint chain that CodeQL (py/path-injection)
    tracks from the HTTP parameter.
    """
    try:
        parts = _sanitize_path_parts(filepath)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail="Invalid path characters") from exc

    # Reconstruct entirely from the safe root + validated parts (no raw user input)
    resolved = _DB_ROOT.joinpath(*parts).resolve()

    # Belt-and-suspenders boundary check
    if not resolved.is_relative_to(_DB_ROOT):
        raise HTTPException(status_code=400, detail="Invalid file path")

    return resolved


def _safe_frontend_path(filepath: str) -> Path:
    """
    Resolve filepath inside FRONTEND_DIST; raise 403 on path traversal.

    Same basename()-based sanitisation as _safe_db_path.
    """
    try:
        parts = _sanitize_path_parts(filepath)
    except ValueError as exc:
        raise HTTPException(status_code=403, detail="Forbidden") from exc

    resolved = _FRONTEND_ROOT.joinpath(*parts).resolve()

    if not resolved.is_relative_to(_FRONTEND_ROOT):
        raise HTTPException(status_code=403, detail="Forbidden")

    return resolved


def _require_quarter(quarter: str | None) -> str:
    if not quarter or not _QUARTER_RE.match(quarter):
        raise HTTPException(status_code=422, detail="quarter must be in YYYYQ[1-4] format")
    return quarter


def _require_ticker(ticker: str | None) -> str:
    if not ticker or not _TICKER_RE.match(ticker.upper()):
        raise HTTPException(status_code=422, detail="Invalid ticker format")
    return ticker.upper()


def _require_cusip(cusip: str | None) -> str:
    if not cusip or not _CUSIP_RE.match(cusip.upper()):
        raise HTTPException(status_code=422, detail="CUSIP must be 9 alphanumeric characters")
    return cusip.upper()


# ── Database file serving ──────────────────────────────────────────────────────


@app.get("/database/{filepath:path}")
async def get_database_file(filepath: str):
    file_path = _safe_db_path(filepath)
    if not file_path.exists():
        raise HTTPException(status_code=404, detail=f"File not found: {filepath}")
    content = file_path.read_text(encoding="utf-8")
    media_type = "text/csv" if filepath.endswith(".csv") else "application/json"
    return Response(content=content, media_type=media_type)


@app.put("/database/{filepath:path}")
async def put_database_file(filepath: str, request: Request):
    file_path = _safe_db_path(filepath)
    file_path.parent.mkdir(parents=True, exist_ok=True)
    body = await request.body()
    file_path.write_text(body.decode("utf-8"), encoding="utf-8")
    return {"ok": True}


# ── Quarter fund listing ───────────────────────────────────────────────────────


@app.get("/api/database/quarters")
async def list_quarters() -> list[str]:
    """
    List all available quarter folders (YYYYQ[1-4]) in the database directory, sorted chronologically.
    """
    if not DATABASE_DIR.exists():
        return []
    return sorted(
        d.name for d in DATABASE_DIR.iterdir() if d.is_dir() and _QUARTER_RE.match(d.name)
    )


@app.get("/api/database/quarters/latest")
async def latest_quarter() -> dict[str, str | None]:
    """
    Return the most recent quarter present in the database, or {"quarter": None} if empty.

    Centralizes "latest quarter" resolution on the backend so the frontend doesn't have
    to sort the list itself.
    """
    if not DATABASE_DIR.exists():
        return {"quarter": None}
    quarters = sorted(
        d.name for d in DATABASE_DIR.iterdir() if d.is_dir() and _QUARTER_RE.match(d.name)
    )
    return {"quarter": quarters[-1] if quarters else None}


@app.get("/api/database/quarters/{quarter}")
async def list_quarter_funds(quarter: str):
    sanitized_quarter = _require_quarter(quarter)
    quarter_dir = _safe_db_path(sanitized_quarter)
    if not quarter_dir.exists() or not quarter_dir.is_dir():
        raise HTTPException(status_code=404, detail=f"Quarter not found: {sanitized_quarter}")
    return [f.stem for f in sorted(quarter_dir.glob("*.csv"))]


@app.get("/api/database/quarters/{quarter}/analysis")
async def quarter_analysis_endpoint(quarter: str) -> list[dict[str, object]]:
    """
    Return the per-ticker aggregated quarter analysis.

    Replaces the per-fund CSV fan-out previously done client-side: the frontend gets
    a pre-aggregated leaderboard in a single request instead of fetching every fund's CSV.
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


# ── Stock price history ────────────────────────────────────────────────────────


@app.get("/api/stocks/{ticker}/history")
async def stock_price_history(ticker: str, range: str = "5y") -> dict:
    """
    Return monthly close prices for the given ticker over the requested range.

    `range` accepts yfinance period strings (e.g. "1y", "3y", "5y", "10y", "max").
    Output: {"ticker": "...", "range": "...", "points": [{"date": "YYYY-MM-DD", "close": float}, ...]}
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


# ── .env read/write ────────────────────────────────────────────────────────────


@app.get("/api/settings/env")
async def get_env():
    if not ENV_FILE.exists():
        return {}
    result = {}
    for line in ENV_FILE.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            key, _, value = line.partition("=")
            result[key.strip()] = value.strip()
    return result


@app.put("/api/settings/env")
async def put_env(request: Request):
    data: dict = await request.json()
    lines = [f"{k}={v}" for k, v in data.items()]
    ENV_FILE.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return {"ok": True}


# ── AI endpoints ───────────────────────────────────────────────────────────────


def _df_to_json_safe_records(df: "pd.DataFrame") -> list[dict[str, object]]:
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
    return cleaned.where(cleaned.notna(), None).to_dict(orient="records")  # type: ignore[arg-type,return-value]


@app.post("/api/ai/promise-score")
@limiter.limit("10/minute")
async def ai_promise_score(
    request: Request,
):
    """
    Score-rank the top N stocks for a quarter via the configured AI provider.
    Auth disabled for local single-user mode; falls back to env-var API keys.
    """
    from app.ai.agent import AnalystAgent

    body = await request.json()
    quarter = _require_quarter(body.get("quarter"))
    top_n = body.get("top_n", 20)
    provider_id = body.get("provider_id")
    ai_client = _build_ai_client(provider_id, None, body.get("model_id"))
    agent = AnalystAgent(quarter=quarter, ai_client=ai_client)
    df = agent.generate_scored_list(top_n=top_n)
    return _df_to_json_safe_records(df)


@app.post("/api/ai/due-diligence")
@limiter.limit("10/minute")
async def ai_due_diligence(
    request: Request,
):
    """
    AI due-diligence on one ticker for one quarter. Auth disabled for local
    single-user mode; falls back to env-var API keys.
    """
    from app.ai.agent import AnalystAgent

    body = await request.json()
    ticker = _require_ticker(body.get("ticker"))
    quarter = _require_quarter(body.get("quarter"))
    provider_id = body.get("provider_id")
    ai_client = _build_ai_client(provider_id, None, body.get("model_id"))
    agent = AnalystAgent(quarter=quarter, ai_client=ai_client)
    return agent.run_stock_due_diligence(ticker=ticker)


# ── Database operations ────────────────────────────────────────────────────────


@app.post("/api/database/fetch")
async def database_fetch(request: Request):
    from database.updater import run_all_funds_report

    body = await request.json()
    fetch_type = body.get("type", "all")
    if fetch_type == "all":
        run_all_funds_report()
    else:
        raise HTTPException(status_code=422, detail=f"Unknown fetch type: {fetch_type}")
    return {"ok": True}


@app.post("/api/update-all")
async def update_all():
    from database.updater import run_all_funds_report

    run_all_funds_report()
    return {"message": "All 13F reports generated successfully"}


@app.post("/api/update-all/stream")
async def update_all_stream():
    from database.updater import run_all_funds_report

    return _make_sse_stream(
        lambda: (run_all_funds_report(), "All 13F reports generated successfully")[1]
    )


@app.post("/api/fetch-nq")
async def fetch_nq():
    from database.updater import run_fetch_nq_filings

    run_fetch_nq_filings()
    return {"message": "Non-quarterly filings fetched successfully"}


@app.post("/api/fetch-nq/stream")
async def fetch_nq_stream():
    from database.updater import run_fetch_nq_filings

    return _make_sse_stream(
        lambda: (run_fetch_nq_filings(), "Non-quarterly filings fetched successfully")[1]
    )


@app.post("/api/update-ticker")
async def update_ticker_endpoint(request: Request):
    from app.utils.database import update_ticker

    body = await request.json()
    old_ticker = _require_ticker(body.get("old_ticker", "").strip())
    new_ticker = _require_ticker(body.get("new_ticker", "").strip())
    new_company = body.get("new_company", "").strip() or None
    update_ticker(old_ticker, new_ticker, new_company=new_company)
    return {"message": f"Ticker updated: {old_ticker} → {new_ticker}"}


@app.post("/api/update-cusip-ticker")
async def update_cusip_ticker_endpoint(request: Request):
    from app.utils.database import update_ticker_for_cusip

    body = await request.json()
    cusip = _require_cusip(body.get("cusip", "").strip())
    new_ticker = _require_ticker(body.get("new_ticker", "").strip())
    new_company = body.get("new_company", "").strip() or None
    update_ticker_for_cusip(cusip, new_ticker, new_company=new_company)
    return {"message": f"CUSIP {cusip} ticker updated to {new_ticker}"}


@app.get("/api/detect-ticker-changes")
async def detect_ticker_changes_endpoint():
    """
    Fetches recent symbol changes from NASDAQ and returns those applicable to stocks.csv.
    """
    from app.stocks.libraries.nasdaq import Nasdaq
    from app.utils.database import find_cusips_for_ticker

    changes = Nasdaq.get_symbol_changes()
    applicable = []
    for change in changes:
        old_symbol = change.get("oldSymbol", "")
        matching = find_cusips_for_ticker(old_symbol)
        if matching:
            applicable.append(
                {
                    "oldSymbol": old_symbol,
                    "newSymbol": change.get("newSymbol", ""),
                    "companyName": change.get("companyName", ""),
                    "cusips": [s["CUSIP"] for s in matching],
                }
            )
    return {"total_changes": len(changes), "applicable": applicable}


@app.post("/api/apply-ticker-changes")
async def apply_ticker_changes_endpoint():
    """
    Detects and applies all applicable ticker changes from NASDAQ across the entire database.
    """
    from app.stocks.libraries.nasdaq import Nasdaq
    from app.stocks.libraries.yfinance import YFinance
    from app.utils.database import find_cusips_for_ticker, update_ticker

    changes = Nasdaq.get_symbol_changes()
    applied = []
    for change in changes:
        old_symbol = change.get("oldSymbol", "")
        new_symbol = change.get("newSymbol", "")
        matching = find_cusips_for_ticker(old_symbol)
        if matching:
            company = YFinance.get_company("", ticker=new_symbol) or change.get("companyName", "")
            update_ticker(old_symbol, new_symbol, new_company=company)
            applied.append({"old": old_symbol, "new": new_symbol, "companyName": company})
    return {"applied": applied}


# ── AI streaming endpoints ─────────────────────────────────────────────────

# ── Per-request stdout capture for SSE streaming ──────────────────────────────
#
# Multi-tenant safety: instead of redirecting sys.stdout globally (and serializing
# requests with a lock to avoid output mixing), we install a single stdout wrapper
# at startup that consults a ContextVar. Each SSE handler sets its own queue in
# the contextvar before running the target function in a thread; the thread
# inherits the context, so prints from that thread route to the right queue.
# Prints from anywhere else (uvicorn logs, CLI mode, other endpoints) see no
# queue and pass through to the original stdout.
#
# Result: no global lock, concurrent SSE streams are fully isolated.

_request_log_q: contextvars.ContextVar[queue.SimpleQueue | None] = contextvars.ContextVar(
    "_request_log_q", default=None
)


class _ContextAwareStdout:
    """
    sys.stdout replacement that routes prints to a per-context queue when set,
    falling back to the original stdout otherwise.
    """

    def __init__(self, fallback):
        self._fallback = fallback

    def write(self, text: str) -> int:
        q = _request_log_q.get()
        if q is None:
            return self._fallback.write(text)
        for line in text.splitlines():
            if line.strip():
                q.put(("log", line))
        return len(text)

    def flush(self) -> None:
        self._fallback.flush()

    def __getattr__(self, name):
        # Delegate everything else (encoding, fileno, isatty, ...) to fallback.
        return getattr(self._fallback, name)


# Install once at module import. Idempotent: re-importing won't re-wrap.
if not isinstance(sys.stdout, _ContextAwareStdout):
    sys.stdout = _ContextAwareStdout(sys.stdout)


def _make_sse_stream(target_fn):
    """
    Run target_fn in a thread, capture its stdout via contextvar, and stream
    each line as SSE. Concurrent calls are fully isolated — no shared lock.
    """
    log_q: queue.SimpleQueue = queue.SimpleQueue()

    def run():
        """
        Executes target_fn with the per-request log queue bound to a contextvar.
        Threads spawned by target_fn inherit the context, so their prints route
        to this queue too.
        """
        token = _request_log_q.set(log_q)
        try:
            result = target_fn()
            log_q.put(("result", result))
        except Exception as e:
            log_q.put(("error", str(e)))
        finally:
            _request_log_q.reset(token)

    threading.Thread(target=run, daemon=True).start()

    async def generate():
        loop = asyncio.get_event_loop()
        while True:
            item = await loop.run_in_executor(None, log_q.get)
            kind, payload = item
            if kind == "log":
                yield f"data: {json.dumps({'type': 'log', 'text': payload})}\n\n"
            elif kind == "result":
                yield f"data: {json.dumps({'type': 'result', 'data': payload})}\n\n"
                break
            elif kind == "error":
                yield f"data: {json.dumps({'type': 'error', 'message': payload})}\n\n"
                break

    return StreamingResponse(
        generate(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@app.post("/api/ai/promise-score/stream")
@limiter.limit("10/minute")
async def ai_promise_score_stream(
    request: Request,
):
    """
    SSE-streamed Promise Score analysis. Auth disabled for local single-user
    mode; falls back to env-var API keys.
    """
    from app.ai.agent import AnalystAgent

    body = await request.json()
    quarter = _require_quarter(body.get("quarter"))
    top_n = body.get("top_n", 20)
    provider_id = body.get("provider_id")
    ai_client = _build_ai_client(provider_id, None, body.get("model_id"))

    def run():
        agent = AnalystAgent(quarter=quarter, ai_client=ai_client)
        df = agent.generate_scored_list(top_n=top_n)
        return _df_to_json_safe_records(df)

    return _make_sse_stream(run)


@app.post("/api/ai/due-diligence/stream")
@limiter.limit("10/minute")
async def ai_due_diligence_stream(
    request: Request,
):
    """
    SSE-streamed due diligence. Auth disabled for local single-user mode;
    falls back to env-var API keys.
    """
    from app.ai.agent import AnalystAgent

    body = await request.json()
    ticker = _require_ticker(body.get("ticker"))
    quarter = _require_quarter(body.get("quarter"))
    provider_id = body.get("provider_id")
    ai_client = _build_ai_client(provider_id, None, body.get("model_id"))

    def run():
        agent = AnalystAgent(quarter=quarter, ai_client=ai_client)
        return agent.run_stock_due_diligence(ticker=ticker)

    return _make_sse_stream(run)


# ── Static frontend ────────────────────────────────────────────────────────────


@app.exception_handler(StarletteHTTPException)
async def http_exception_handler(request: Request, exc: StarletteHTTPException):
    # For 404s on non-API routes, serve the SPA index.html (React Router handles routing)
    if exc.status_code == 404 and not request.url.path.startswith(("/api/", "/database/")):
        index = _FRONTEND_ROOT / "index.html"
        if index.exists():
            return FileResponse(str(index))
    return JSONResponse({"detail": exc.detail}, status_code=exc.status_code)


@app.get("/{full_path:path}")
async def serve_spa(full_path: str):
    try:
        if full_path:
            file_path = _safe_frontend_path(full_path)
            if file_path.exists() and file_path.is_file():
                return FileResponse(str(file_path))
    except (HTTPException, ValueError, OSError):
        pass

    # Fallback to index.html for SPA routes (React Router handles the rest)
    index = _FRONTEND_ROOT / "index.html"
    if index.exists():
        return FileResponse(str(index))
    raise HTTPException(
        status_code=503, detail="Frontend not built. Run: cd app/frontend && npm run build"
    )


# ── AI client factory ──────────────────────────────────────────────────────────


def _build_ai_client(provider_id: str, api_key: str | None, model_id: str | None = None):
    """
    Build the AI client for the requested provider, using the user's BYOK key.

    No env-var fallback: callers (the /api/ai/* endpoints) must look up the
    user's stored key first and pass it in. Unknown provider → 400.
    """
    from app.ai.clients import (
        GitHubClient,
        GoogleAIClient,
        GroqClient,
        HuggingFaceClient,
        OpenRouterClient,
    )

    client_map = {
        "github": GitHubClient,
        "google": GoogleAIClient,
        "groq": GroqClient,
        "huggingface": HuggingFaceClient,
        "openrouter": OpenRouterClient,
    }
    client_cls = client_map.get(provider_id)
    if client_cls is None:
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported provider {provider_id!r}. Allowed: {sorted(client_map.keys())}",
        )

    kwargs: dict = {}
    if model_id is not None:
        kwargs["model"] = model_id
    if api_key is not None:
        kwargs["api_key"] = api_key
    return client_cls(**kwargs)


async def _resolve_byok_key(user: "User", provider_id: str) -> str:
    """
    Look up the requesting user's stored API key for the provider. Raises
    HTTPException 400 with a helpful message if the user hasn't added one
    (the FE is expected to redirect them to Settings → API Keys).
    """
    from app.auth import api_keys as api_keys_svc

    if not provider_id:
        raise HTTPException(status_code=400, detail="provider_id is required")

    async with AsyncSessionLocal() as session:
        try:
            return await api_keys_svc.get_for_use(session, user, provider_id)
        except api_keys_svc.NoSuchApiKeyError:
            raise HTTPException(
                status_code=400,
                detail=(
                    f"No API key configured for provider {provider_id!r}. "
                    "Add one in Settings → API Keys."
                ),
            ) from None
        finally:
            await session.commit()  # persist last_used_at update from get_for_use
