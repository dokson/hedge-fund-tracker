"""
Per-request stdout capture for SSE streaming.

Multi-tenant safety: instead of redirecting sys.stdout globally (and serializing
requests with a lock to avoid output mixing), we install a single stdout wrapper
at import that consults a ContextVar. Each SSE handler sets its own queue in the
contextvar before running the target function in a thread; the thread inherits
the context, so prints from that thread route to the right queue. Prints from
anywhere else (uvicorn logs, CLI mode, other endpoints) see no queue and pass
through to the original stdout.

Result: no global lock, concurrent SSE streams are fully isolated.

This module is imported by app.server (and the AI/admin routers), so the stdout
wrapper installs once at app startup — keep it imported somewhere on the boot
path or SSE log capture silently stops working.
"""

from __future__ import annotations

import asyncio
import contextvars
import json
import queue
import sys
import threading
from collections.abc import Callable

from fastapi.responses import StreamingResponse
from tenacity import RetryError

_request_log_q: contextvars.ContextVar[queue.SimpleQueue | None] = contextvars.ContextVar(
    "_request_log_q", default=None
)


class _ContextAwareStdout:
    """
    sys.stdout replacement that routes prints to a per-context queue when set,
    falling back to the original stdout otherwise.
    """

    def __init__(self, fallback):
        """
        Wrap the stream that receives writes made outside any SSE request.
        """
        self.fallback = fallback

    @property
    def capturing(self) -> bool:
        """
        True while the current context's writes go to an SSE request queue.
        """
        return _request_log_q.get() is not None

    def write(self, text: str) -> int:
        """
        Route non-blank lines to the current request's queue, or pass through.
        """
        q = _request_log_q.get()
        if q is None:
            return self.fallback.write(text)
        for line in text.splitlines():
            if line.strip():
                q.put(("log", line))
        return len(text)

    def flush(self) -> None:
        """
        Flush the fallback stream.
        """
        self.fallback.flush()

    def __getattr__(self, name):
        """
        Delegate every other attribute (encoding, fileno, isatty, ...) to the fallback.
        """
        return getattr(self.fallback, name)


# Install once at module import. Idempotent: re-importing won't re-wrap.
if not isinstance(sys.stdout, _ContextAwareStdout):
    sys.stdout = _ContextAwareStdout(sys.stdout)


RATE_LIMIT_MESSAGE = "Yahoo Finance rate limit reached; retry in a few minutes."


def is_rate_limit_error(exc: BaseException) -> bool:
    """
    True when ``exc`` is a Yahoo Finance rate limit.
    """
    # Imported lazily: this module is on the boot path and yfinance is heavy.
    from yfinance.exceptions import YFRateLimitError

    return isinstance(exc, YFRateLimitError)


def describe_retry_error(exc: RetryError) -> str:
    """
    Describe an exhausted retry by its last attempt's failure, not tenacity's Future repr.
    """
    last = exc.last_attempt.exception() if exc.last_attempt.failed else None
    if last is None:
        return "retries exhausted"
    return str(last) or last.__class__.__name__


def _describe_error(exc: BaseException) -> str:
    """
    Turn an exception into the message shown to the SSE client.
    """
    if isinstance(exc, RetryError):
        return describe_retry_error(exc)
    if is_rate_limit_error(exc):
        return RATE_LIMIT_MESSAGE
    return str(exc) or exc.__class__.__name__


def _run_sse_target(target_fn: Callable[[], object], log_q: queue.SimpleQueue) -> None:
    """
    Execute target_fn with the per-request log queue bound to a contextvar, and
    guarantee a terminal ("result"/"error") item is enqueued on every exit path.

    Threads spawned by target_fn inherit the context, so their prints route to
    this queue too. Catching BaseException (not just Exception) is load-bearing:
    if a SystemExit/KeyboardInterrupt escaped without a terminal item, the SSE
    consumer's blocking `log_q.get()` would hang forever — leaking an executor
    thread and an open HTTP connection.
    """
    token = _request_log_q.set(log_q)
    emitted = False
    try:
        result = target_fn()
        log_q.put(("result", result))
        emitted = True
    except BaseException as e:  # noqa: BLE001 — consumer must be signalled on every failure
        log_q.put(("error", _describe_error(e)))
        emitted = True
    finally:
        _request_log_q.reset(token)
        if not emitted:
            log_q.put(("error", "stream terminated unexpectedly"))


def _queue_get_with_timeout(log_q: queue.SimpleQueue) -> tuple | None:
    """
    Pop the next queue item, returning None after a short poll timeout.

    The SSE consumer must never block an executor thread indefinitely: when a
    client disconnects the async generator is cancelled, but a thread parked
    in a timeout-less ``get()`` would stay blocked until the worker finishes
    (or forever, if it hangs). Polling bounds that leak to one timeout window.
    """
    try:
        return log_q.get(timeout=1.0)
    except queue.Empty:
        return None


def _make_sse_stream(target_fn: Callable[[], object]) -> StreamingResponse:
    """
    Run target_fn in a thread, capture its stdout via contextvar, and stream
    each line as SSE. Concurrent calls are fully isolated — no shared lock.
    """
    log_q: queue.SimpleQueue = queue.SimpleQueue()

    # Copy the context so the worker's log records keep the request id.
    threading.Thread(
        target=contextvars.copy_context().run,
        args=(_run_sse_target, target_fn, log_q),
        daemon=True,
    ).start()

    async def generate():
        """
        Yield queued log lines as SSE events until a result or error arrives.
        """
        loop = asyncio.get_running_loop()
        while True:
            item = await loop.run_in_executor(None, _queue_get_with_timeout, log_q)
            if item is None:
                continue
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
