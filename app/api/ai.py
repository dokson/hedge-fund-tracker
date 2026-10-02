"""
AI analysis endpoints under /api/ai: Promise Score ranking and per-ticker due
diligence, in both blocking and SSE-streamed variants.

Key resolution: an authenticated caller's stored BYOK key wins; anonymous (or
key-less) callers fall back to the operator's env-var keys only in local
single-user mode. In a production posture anonymous AI calls are rejected.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.concurrency import run_in_threadpool
from fastapi.responses import StreamingResponse
from tenacity import RetryError

from app.api.common import (
    _df_to_json_safe_records,
    _require_quarter,
    _require_ticker,
    limiter,
)
from app.api.sse import (
    RATE_LIMIT_MESSAGE,
    _make_sse_stream,
    describe_retry_error,
    is_rate_limit_error,
)
from app.auth.dependencies import current_optional_user
from app.db.session import AsyncSessionLocal
from app.utils.logger import get_logger

if TYPE_CHECKING:
    from collections.abc import Callable

    from app.ai.clients.base_client import AIClient
    from app.db.models import User

logger = get_logger(__name__)

router = APIRouter(tags=["ai"])

# Provider ids that no longer exist. A stored user config may still point at one,
# so we degrade to the default instead of failing the request.
RETIRED_PROVIDERS: frozenset[str] = frozenset({"github"})
DEFAULT_PROVIDER_ID = "google"


def _resolve_provider(provider_id: str, model_id: str | None) -> tuple[str, str | None]:
    """
    Map a retired provider onto the default one, dropping its model id (which
    belongs to the retired provider) so the fallback client uses its own.
    """
    if provider_id in RETIRED_PROVIDERS:
        logger.warning(
            "Provider %r has been retired; falling back to %r.", provider_id, DEFAULT_PROVIDER_ID
        )
        return DEFAULT_PROVIDER_ID, None
    return provider_id, model_id


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
        GoogleAIClient,
        GroqClient,
        HuggingFaceClient,
        OpenRouterClient,
    )

    client_map: dict[str, Callable[..., AIClient]] = {
        "google": GoogleAIClient,
        "groq": GroqClient,
        "huggingface": HuggingFaceClient,
        "openrouter": OpenRouterClient,
    }
    provider_id, model_id = _resolve_provider(provider_id, model_id)
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


_DEFAULT_TOP_N = 20
_MAX_TOP_N = 50


@dataclass(frozen=True)
class _AIRequest:
    """
    Validated inputs shared by the AI endpoints.
    """

    quarter: str
    ai_client: AIClient
    ticker: str | None = None
    top_n: int = _DEFAULT_TOP_N


def _parse_top_n(value: object) -> int:
    """
    Coerce ``top_n`` to an int in ``1.._MAX_TOP_N``; anything else is a 422.
    """
    if isinstance(value, bool) or not isinstance(value, int | str):
        raise HTTPException(status_code=422, detail="top_n must be an integer")
    try:
        top_n = int(value)
    except ValueError:
        raise HTTPException(status_code=422, detail="top_n must be an integer") from None
    if not 1 <= top_n <= _MAX_TOP_N:
        raise HTTPException(status_code=422, detail=f"top_n must be between 1 and {_MAX_TOP_N}")
    return top_n


def _str_field(body: dict[str, object], key: str) -> str | None:
    """
    Return a body field when it is a string; any other type reads as absent.
    """
    value = body.get(key)
    return value if isinstance(value, str) else None


async def _parse_ai_request(
    request: Request, user: User | None, *, with_ticker: bool = False, with_top_n: bool = False
) -> _AIRequest:
    """
    Validate an AI request body and build its client, rejecting a non-object body with 422.
    """
    try:
        body = await request.json()
    except ValueError:
        raise HTTPException(status_code=422, detail="Request body must be valid JSON") from None
    if not isinstance(body, dict):
        raise HTTPException(status_code=422, detail="Request body must be a JSON object")

    ticker = _require_ticker(_str_field(body, "ticker")) if with_ticker else None
    quarter = _require_quarter(_str_field(body, "quarter"))
    top_n = _parse_top_n(body.get("top_n", _DEFAULT_TOP_N)) if with_top_n else _DEFAULT_TOP_N
    provider_id, model_id = _resolve_provider(
        _str_field(body, "provider_id") or "", _str_field(body, "model_id")
    )
    api_key = await _resolve_request_key(user, provider_id)
    ai_client = _build_ai_client(provider_id, api_key, model_id)
    return _AIRequest(quarter=quarter, ai_client=ai_client, ticker=ticker, top_n=top_n)


def _scored_list(req: _AIRequest) -> list[dict[str, object]]:
    """
    Run the Promise Score ranking for a validated request.
    """
    from app.ai.agent import AnalystAgent

    agent = AnalystAgent(quarter=req.quarter, ai_client=req.ai_client)
    return _df_to_json_safe_records(agent.generate_scored_list(top_n=req.top_n))


def _due_diligence(req: _AIRequest) -> dict[str, object]:
    """
    Run due diligence for a validated request.
    """
    from app.ai.agent import AnalystAgent

    assert req.ticker is not None
    agent = AnalystAgent(quarter=req.quarter, ai_client=req.ai_client)
    return agent.run_stock_due_diligence(ticker=req.ticker)


@router.post("/api/ai/promise-score")
@limiter.limit("10/minute")
async def ai_promise_score(
    request: Request,
    user: User | None = Depends(current_optional_user),
) -> list[dict[str, object]]:
    """
    Score-rank the top N stocks for a quarter via the configured AI provider.

    Raises:
        HTTPException: 503 when Yahoo Finance rate-limits the price lookups.
    """
    req = await _parse_ai_request(request, user, with_top_n=True)
    try:
        return await run_in_threadpool(_scored_list, req)
    except Exception as exc:
        if is_rate_limit_error(exc):
            raise HTTPException(status_code=503, detail=RATE_LIMIT_MESSAGE) from exc
        raise


@router.post("/api/ai/due-diligence")
@limiter.limit("10/minute")
async def ai_due_diligence(
    request: Request,
    user: User | None = Depends(current_optional_user),
) -> dict[str, object]:
    """
    AI due-diligence on one ticker for one quarter.

    Raises:
        HTTPException: 502 when the provider never returns a valid answer.
    """
    req = await _parse_ai_request(request, user, with_ticker=True)
    try:
        return await run_in_threadpool(_due_diligence, req)
    except RetryError as exc:
        raise HTTPException(
            status_code=502,
            detail=f"AI provider returned no valid answer: {describe_retry_error(exc)}",
        ) from exc


@router.post("/api/ai/promise-score/stream")
@limiter.limit("10/minute")
async def ai_promise_score_stream(
    request: Request,
    user: User | None = Depends(current_optional_user),
) -> StreamingResponse:
    """
    SSE-streamed Promise Score analysis.
    """
    req = await _parse_ai_request(request, user, with_top_n=True)
    return _make_sse_stream(lambda: _scored_list(req))


@router.post("/api/ai/due-diligence/stream")
@limiter.limit("10/minute")
async def ai_due_diligence_stream(
    request: Request,
    user: User | None = Depends(current_optional_user),
) -> StreamingResponse:
    """
    SSE-streamed due diligence.
    """
    req = await _parse_ai_request(request, user, with_ticker=True)
    return _make_sse_stream(lambda: _due_diligence(req))
