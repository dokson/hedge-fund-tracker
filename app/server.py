import asyncio
import json
import os
import queue
import sys
import threading
from pathlib import Path

# Fix terminal width for output streamed to the web UI
os.environ.setdefault("COLUMNS", "80")

from fastapi import FastAPI, HTTPException, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from fastapi.staticfiles import StaticFiles

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


# ── Database file serving ──────────────────────────────────────────────────────

@app.get("/database/{filepath:path}")
async def get_database_file(filepath: str):
    file_path = DATABASE_DIR / filepath
    if not file_path.exists():
        raise HTTPException(status_code=404, detail=f"File not found: {filepath}")
    content = file_path.read_text(encoding="utf-8")
    media_type = "text/csv" if filepath.endswith(".csv") else "application/json"
    return Response(content=content, media_type=media_type)


@app.put("/database/{filepath:path}")
async def put_database_file(filepath: str, request: Request):
    file_path = DATABASE_DIR / filepath
    file_path.parent.mkdir(parents=True, exist_ok=True)
    body = await request.body()
    file_path.write_text(body.decode("utf-8"), encoding="utf-8")
    return {"ok": True}


# ── Quarter fund listing ───────────────────────────────────────────────────────

@app.get("/api/database/quarters/{quarter}")
async def list_quarter_funds(quarter: str):
    quarter_dir = DATABASE_DIR / quarter
    if not quarter_dir.exists() or not quarter_dir.is_dir():
        raise HTTPException(status_code=404, detail=f"Quarter not found: {quarter}")
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
    quarter = body.get("quarter")
    top_n = body.get("top_n", 20)
    if not quarter:
        raise HTTPException(status_code=422, detail="quarter is required")
    ai_client = _build_ai_client(body.get("model_id"), body.get("provider_id"))
    agent = AnalystAgent(quarter=quarter, ai_client=ai_client)
    df = agent.generate_scored_list(top_n=top_n)
    return df.to_dict(orient="records")


@app.post("/api/ai/due-diligence")
async def ai_due_diligence(request: Request):
    from app.ai.agent import AnalystAgent
    body = await request.json()
    ticker = body.get("ticker")
    quarter = body.get("quarter")
    if not ticker or not quarter:
        raise HTTPException(status_code=422, detail="ticker and quarter are required")
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
    old_ticker = body.get("old_ticker", "").strip().upper()
    new_ticker = body.get("new_ticker", "").strip().upper()
    if not old_ticker or not new_ticker:
        raise HTTPException(status_code=422, detail="old_ticker and new_ticker are required")
    update_ticker(old_ticker, new_ticker)
    return {"message": f"Ticker updated: {old_ticker} → {new_ticker}"}


@app.post("/api/update-cusip-ticker")
async def update_cusip_ticker_endpoint(request: Request):
    from app.utils.database import update_ticker_for_cusip
    body = await request.json()
    cusip = body.get("cusip", "").strip()
    new_ticker = body.get("new_ticker", "").strip().upper()
    if not cusip or not new_ticker:
        raise HTTPException(status_code=422, detail="cusip and new_ticker are required")
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
    quarter = body.get("quarter")
    top_n = body.get("top_n", 20)
    if not quarter:
        raise HTTPException(status_code=422, detail="quarter is required")
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
    ticker = body.get("ticker")
    quarter = body.get("quarter")
    if not ticker or not quarter:
        raise HTTPException(status_code=422, detail="ticker and quarter are required")
    ai_client = _build_ai_client(body.get("model_id"), body.get("provider_id"))

    def run():
        agent = AnalystAgent(quarter=quarter, ai_client=ai_client)
        return agent.run_stock_due_diligence(ticker=ticker)

    return _make_sse_stream(run)


# ── Static frontend ────────────────────────────────────────────────────────────

if FRONTEND_DIST.exists():
    app.mount("/", StaticFiles(directory=str(FRONTEND_DIST), html=True), name="frontend")


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
