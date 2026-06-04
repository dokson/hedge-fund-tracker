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
        log_q.put(("error", str(e) or e.__class__.__name__))
        emitted = True
    finally:
        _request_log_q.reset(token)
        if not emitted:
            log_q.put(("error", "stream terminated unexpectedly"))


def _make_sse_stream(target_fn: Callable[[], object]) -> StreamingResponse:
    """
    Run target_fn in a thread, capture its stdout via contextvar, and stream
    each line as SSE. Concurrent calls are fully isolated — no shared lock.
    """
    log_q: queue.SimpleQueue = queue.SimpleQueue()

    threading.Thread(target=_run_sse_target, args=(target_fn, log_q), daemon=True).start()

    async def generate():
        loop = asyncio.get_running_loop()
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
