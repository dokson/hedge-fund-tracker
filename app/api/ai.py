"""
AI analysis endpoints under /api/ai: Promise Score ranking and per-ticker due
diligence, in both blocking and SSE-streamed variants.

Auth is disabled for local single-user mode; clients pass ``provider_id`` +
``model_id`` and the backend builds the matching client (env-var keys).
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from fastapi import APIRouter, HTTPException, Request
from fastapi.concurrency import run_in_threadpool

from app.api.common import (
    _df_to_json_safe_records,
    _require_quarter,
    _require_ticker,
    limiter,
)
from app.api.sse import _make_sse_stream
from app.db.session import AsyncSessionLocal

if TYPE_CHECKING:
    from fastapi.responses import StreamingResponse

    from app.ai.clients.base_client import AIClient
    from app.db.models import User

router = APIRouter(tags=["ai"])


def _build_ai_client(
    provider_id: str, api_key: str | None, model_id: str | None = None
) -> AIClient:
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


async def _resolve_byok_key(user: User, provider_id: str) -> str:
    """
    Look up the requesting user's stored API key for the provider. Raises
    HTTPException 400 with a helpful message if the user hasn't added one
    (the FE is expected to redirect them to Settings → API Keys).

    Not yet wired into the endpoints: reserved for the planned BYOK flow, where
    /api/ai/* will resolve the caller's stored key instead of env-var fallback.
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


@router.post("/api/ai/promise-score")
@limiter.limit("10/minute")
async def ai_promise_score(
    request: Request,
) -> list[dict[str, object]]:
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

    # Offload the blocking AI/analysis work so it doesn't stall the event loop.
    def _run() -> list[dict[str, object]]:
        agent = AnalystAgent(quarter=quarter, ai_client=ai_client)
        df = agent.generate_scored_list(top_n=top_n)
        return _df_to_json_safe_records(df)

    return await run_in_threadpool(_run)


@router.post("/api/ai/due-diligence")
@limiter.limit("10/minute")
async def ai_due_diligence(
    request: Request,
) -> dict[str, object]:
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

    # Offload the blocking AI/analysis work so it doesn't stall the event loop.
    def _run() -> dict[str, object]:
        agent = AnalystAgent(quarter=quarter, ai_client=ai_client)
        return agent.run_stock_due_diligence(ticker=ticker)

    return await run_in_threadpool(_run)


@router.post("/api/ai/promise-score/stream")
@limiter.limit("10/minute")
async def ai_promise_score_stream(
    request: Request,
) -> StreamingResponse:
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


@router.post("/api/ai/due-diligence/stream")
@limiter.limit("10/minute")
async def ai_due_diligence_stream(
    request: Request,
) -> StreamingResponse:
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
