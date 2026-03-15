import asyncio
import json
import os
import queue
import re
import sys
import threading
from pathlib import Path

# Fix terminal width for output streamed to the web UI
os.environ.setdefault("COLUMNS", "80")

from fastapi import FastAPI, HTTPException, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, StreamingResponse

DATABASE_DIR = Path(__file__).parent.parent / "database"
FRONTEND_DIST = Path(__file__).parent / "frontend" / "dist"
ENV_FILE = Path(__file__).parent.parent / ".env"

app = FastAPI(title="Hedge Fund Tracker")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


# ── Input validation helpers ───────────────────────────────────────────────────

_DB_ROOT = DATABASE_DIR.resolve()
_FRONTEND_ROOT = FRONTEND_DIST.resolve()
_QUARTER_RE = re.compile(r"^\d{4}Q[1-4]$")
_TICKER_RE  = re.compile(r"^[A-Z0-9.\-]{1,10}$")
_CUSIP_RE   = re.compile(r"^[A-Z0-9]{9}$")


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
        clean = os.path.basename(part)
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
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid path characters")

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
    except ValueError:
        raise HTTPException(status_code=403, detail="Forbidden")

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

@app.get("/api/database/quarters/{quarter}")
async def list_quarter_funds(quarter: str):
    sanitized_quarter = _require_quarter(quarter)
    quarter_dir = _safe_db_path(sanitized_quarter)
    if not quarter_dir.exists() or not quarter_dir.is_dir():
        raise HTTPException(status_code=404, detail=f"Quarter not found: {sanitized_quarter}")
    return [f.stem for f in sorted(quarter_dir.glob("*.csv"))]


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

@app.post("/api/ai/promise-score")
async def ai_promise_score(request: Request):
    from app.ai.agent import AnalystAgent
    body = await request.json()
    quarter = _require_quarter(body.get("quarter"))
    top_n = body.get("top_n", 20)
    ai_client = _build_ai_client(body.get("model_id"), body.get("provider_id"))
    agent = AnalystAgent(quarter=quarter, ai_client=ai_client)
    df = agent.generate_scored_list(top_n=top_n)
    return df.to_dict(orient="records")


@app.post("/api/ai/due-diligence")
async def ai_due_diligence(request: Request):
    from app.ai.agent import AnalystAgent
    body = await request.json()
    ticker = _require_ticker(body.get("ticker"))
    quarter = _require_quarter(body.get("quarter"))
    ai_client = _build_ai_client(body.get("model_id"), body.get("provider_id"))
    agent = AnalystAgent(quarter=quarter, ai_client=ai_client)
    result = agent.run_stock_due_diligence(ticker=ticker)
    return result


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
    return _make_sse_stream(lambda: (run_all_funds_report(), "All 13F reports generated successfully")[1])


@app.post("/api/fetch-nq")
async def fetch_nq():
    from database.updater import run_fetch_nq_filings
    run_fetch_nq_filings()
    return {"message": "Non-quarterly filings fetched successfully"}


@app.post("/api/fetch-nq/stream")
async def fetch_nq_stream():
    from database.updater import run_fetch_nq_filings
    return _make_sse_stream(lambda: (run_fetch_nq_filings(), "Non-quarterly filings fetched successfully")[1])


@app.post("/api/update-ticker")
async def update_ticker_endpoint(request: Request):
    from app.utils.database import update_ticker
    body = await request.json()
    old_ticker = _require_ticker(body.get("old_ticker", "").strip())
    new_ticker = _require_ticker(body.get("new_ticker", "").strip())
    update_ticker(old_ticker, new_ticker)
    return {"message": f"Ticker updated: {old_ticker} → {new_ticker}"}


@app.post("/api/update-cusip-ticker")
async def update_cusip_ticker_endpoint(request: Request):
    from app.utils.database import update_ticker_for_cusip
    body = await request.json()
    cusip = _require_cusip(body.get("cusip", "").strip())
    new_ticker = _require_ticker(body.get("new_ticker", "").strip())
    update_ticker_for_cusip(cusip, new_ticker)
    return {"message": f"CUSIP {cusip} ticker updated to {new_ticker}"}


# ── AI streaming endpoints ─────────────────────────────────────────────────

def _make_sse_stream(target_fn):
    """Run target_fn in a thread, capture its stdout, and stream each line as SSE."""
    log_q: queue.Queue = queue.SimpleQueue()

    class _Writer:
        def write(self, text: str):
            for line in text.splitlines():
                if line.strip():
                    log_q.put(("log", line))
        def flush(self): pass

    def run():
        old = sys.stdout
        sys.stdout = _Writer()
        try:
            result = target_fn()
            log_q.put(("result", result))
        except Exception as e:
            log_q.put(("error", str(e)))
        finally:
            sys.stdout = old

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
async def ai_promise_score_stream(request: Request):
    from app.ai.agent import AnalystAgent
    body = await request.json()
    quarter = _require_quarter(body.get("quarter"))
    top_n = body.get("top_n", 20)
    ai_client = _build_ai_client(body.get("model_id"), body.get("provider_id"))

    def run():
        agent = AnalystAgent(quarter=quarter, ai_client=ai_client)
        df = agent.generate_scored_list(top_n=top_n)
        return df.to_dict(orient="records")

    return _make_sse_stream(run)


@app.post("/api/ai/due-diligence/stream")
async def ai_due_diligence_stream(request: Request):
    from app.ai.agent import AnalystAgent
    body = await request.json()
    ticker = _require_ticker(body.get("ticker"))
    quarter = _require_quarter(body.get("quarter"))
    ai_client = _build_ai_client(body.get("model_id"), body.get("provider_id"))

    def run():
        agent = AnalystAgent(quarter=quarter, ai_client=ai_client)
        return agent.run_stock_due_diligence(ticker=ticker)

    return _make_sse_stream(run)


# ── Static frontend ────────────────────────────────────────────────────────────

from fastapi.responses import JSONResponse
from fastapi.exceptions import HTTPException as StarletteHTTPException


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
    raise HTTPException(status_code=503, detail="Frontend not built. Run: cd app/frontend && npm run build")


# ── AI client factory ──────────────────────────────────────────────────────────

def _build_ai_client(model_id: str | None = None, provider_id: str | None = None):
    """Build the AI client for the requested provider, falling back to first available."""
    from app.ai.clients import (
        GitHubClient, GoogleAIClient, GroqClient,
        HuggingFaceClient, OpenRouterClient,
    )
    provider_map = {
        "github":      ("GITHUB_TOKEN",       GitHubClient),
        "google":      ("GOOGLE_API_KEY",     GoogleAIClient),
        "groq":        ("GROQ_API_KEY",       GroqClient),
        "huggingface": ("HF_TOKEN",           HuggingFaceClient),
        "openrouter":  ("OPENROUTER_API_KEY", OpenRouterClient),
    }
    # If provider is known, use it directly (if its key is present)
    if provider_id and provider_id in provider_map:
        env_var, ClientClass = provider_map[provider_id]
        if os.getenv(env_var):
            return ClientClass() if model_id is None else ClientClass(model=model_id)
        raise HTTPException(
            status_code=500,
            detail=f"No API key configured for provider '{provider_id}'. Set {env_var} in .env.",
        )
    # Fallback: first available provider
    for env_var, ClientClass in provider_map.values():
        if os.getenv(env_var):
            return ClientClass() if model_id is None else ClientClass(model=model_id)
    raise HTTPException(status_code=500, detail="No AI provider configured. Set at least one API key in .env.")
