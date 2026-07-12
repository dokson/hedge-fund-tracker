"""
AI analysis endpoints under /api/ai: Promise Score ranking and per-ticker due
diligence, in both blocking and SSE-streamed variants.

Key resolution: an authenticated caller's stored BYOK key wins; anonymous (or
key-less) callers fall back to the operator's env-var keys only in local
single-user mode. In a production posture anonymous AI calls are rejected.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.concurrency import run_in_threadpool
from fastapi.responses import StreamingResponse

from app.api.common import (
    _df_to_json_safe_records,
    _require_quarter,
    _require_ticker,
    limiter,
)
from app.api.sse import _make_sse_stream
from app.auth.dependencies import current_optional_user
from app.db.session import AsyncSessionLocal

if TYPE_CHECKING:
    from collections.abc import Callable

    from app.ai.clients.base_client import AIClient
    from app.db.models import User

router = APIRouter(tags=["ai"])


def _build_ai_client(
    provider_id: str, api_key: str | None, model_id: str | None = None
) -> AIClient:
    """
    Build the AI client for the requested provider.

    Callers resolve the key via ``_resolve_request_key`` first; ``None`` lets
    the client fall back to its env-var key (local mode only). Unknown
    provider → 400.
    """
    from app.ai.clients import (
        GitHubClient,
        GoogleAIClient,
        GroqClient,
        HuggingFaceClient,
        OpenRouterClient,
    )

    client_map: dict[str, Callable[..., AIClient]] = {
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


async def _resolve_request_key(user: User | None, provider_id: str) -> str | None:
    """
    Resolve the API key for an AI request.

    An authenticated caller's stored BYOK key wins. Without one, local
    single-user mode (COOKIE_SECURE unset) falls back to the operator's env-var
    keys (``None`` → client env fallback); a production posture rejects
    anonymous callers with 401 and key-less users with a helpful 400 (the FE
    redirects them to Settings → API Keys).
    """
    from app.auth import api_keys as api_keys_svc
    from app.auth import backend

    if user is None:
        if backend.COOKIE_SECURE:
            raise HTTPException(status_code=401, detail="Authentication required")
        return None

    if not provider_id:
        raise HTTPException(status_code=400, detail="provider_id is required")

    async with AsyncSessionLocal() as session:
        try:
            return await api_keys_svc.get_for_use(session, user, provider_id)
        except api_keys_svc.NoSuchApiKeyError:
            if not backend.COOKIE_SECURE:
                return None
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
    user: User | None = Depends(current_optional_user),
) -> list[dict[str, object]]:
    """
    Score-rank the top N stocks for a quarter via the configured AI provider.
    """
    from app.ai.agent import AnalystAgent

    body = await request.json()
    quarter = _require_quarter(body.get("quarter"))
    top_n = body.get("top_n", 20)
    provider_id = body.get("provider_id")
    api_key = await _resolve_request_key(user, provider_id)
    ai_client = _build_ai_client(provider_id, api_key, body.get("model_id"))

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
    user: User | None = Depends(current_optional_user),
) -> dict[str, object]:
    """
    AI due-diligence on one ticker for one quarter.
    """
    from app.ai.agent import AnalystAgent

    body = await request.json()
    ticker = _require_ticker(body.get("ticker"))
    quarter = _require_quarter(body.get("quarter"))
    provider_id = body.get("provider_id")
    api_key = await _resolve_request_key(user, provider_id)
    ai_client = _build_ai_client(provider_id, api_key, body.get("model_id"))

    # Offload the blocking AI/analysis work so it doesn't stall the event loop.
    def _run() -> dict[str, object]:
        agent = AnalystAgent(quarter=quarter, ai_client=ai_client)
        return agent.run_stock_due_diligence(ticker=ticker)

    return await run_in_threadpool(_run)


@router.post("/api/ai/promise-score/stream")
@limiter.limit("10/minute")
async def ai_promise_score_stream(
    request: Request,
    user: User | None = Depends(current_optional_user),
) -> StreamingResponse:
    """
    SSE-streamed Promise Score analysis.
    """
    from app.ai.agent import AnalystAgent

    body = await request.json()
    quarter = _require_quarter(body.get("quarter"))
    top_n = body.get("top_n", 20)
    provider_id = body.get("provider_id")
    api_key = await _resolve_request_key(user, provider_id)
    ai_client = _build_ai_client(provider_id, api_key, body.get("model_id"))

    def run():
        agent = AnalystAgent(quarter=quarter, ai_client=ai_client)
        df = agent.generate_scored_list(top_n=top_n)
        return _df_to_json_safe_records(df)

    return _make_sse_stream(run)


@router.post("/api/ai/due-diligence/stream")
@limiter.limit("10/minute")
async def ai_due_diligence_stream(
    request: Request,
    user: User | None = Depends(current_optional_user),
) -> StreamingResponse:
    """
    SSE-streamed due diligence.
    """
    from app.ai.agent import AnalystAgent

    body = await request.json()
    ticker = _require_ticker(body.get("ticker"))
    quarter = _require_quarter(body.get("quarter"))
    provider_id = body.get("provider_id")
    api_key = await _resolve_request_key(user, provider_id)
    ai_client = _build_ai_client(provider_id, api_key, body.get("model_id"))

    def run():
        agent = AnalystAgent(quarter=quarter, ai_client=ai_client)
        return agent.run_stock_due_diligence(ticker=ticker)

    return _make_sse_stream(run)
