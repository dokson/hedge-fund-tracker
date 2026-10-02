"""
HTTP request correlation, access logging and Prometheus request metrics.
"""

import re
import time
import uuid

from starlette.datastructures import MutableHeaders
from starlette.types import ASGIApp, Message, Receive, Scope, Send

from app.utils.logger import get_logger, log_safe, request_id_var
from app.utils.metrics import HTTP_REQUEST_DURATION, HTTP_REQUESTS

logger = get_logger(__name__)

REQUEST_ID_HEADER = "X-Request-ID"
_SAFE_REQUEST_ID = re.compile(r"[A-Za-z0-9._:-]{1,128}")
_KNOWN_METHODS = frozenset({"GET", "HEAD", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"})
_QUIET_PATHS = frozenset({"/health", "/metrics"})


def _request_id(scope: Scope) -> str:
    """
    Reuse a short, log-safe incoming X-Request-ID, else mint a new one.
    """
    for name, value in scope.get("headers", []):
        if name == b"x-request-id":
            incoming = value.decode("latin-1")
            if _SAFE_REQUEST_ID.fullmatch(incoming):
                return incoming
            break
    return uuid.uuid4().hex


def _route_label(scope: Scope) -> str:
    """
    The matched route template, so path parameters don't mint new series.
    """
    route = scope.get("route")
    return getattr(route, "path", None) or "unmatched"


def _is_quiet(path: str) -> bool:
    """
    Probes, the metrics scrape and static files are kept out of the access log.
    """
    return path in _QUIET_PATHS or "." in path.rsplit("/", 1)[-1]


class RequestContextMiddleware:
    """
    Pure ASGI middleware: binds a request id for the whole request (streaming
    bodies included), echoes it in the response, logs one access line and
    records request count and latency.
    """

    def __init__(self, app: ASGIApp):
        """
        Wrap the downstream ASGI app.
        """
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        """
        Handle one HTTP request; other scope types pass straight through.
        """
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        request_id = _request_id(scope)
        token = request_id_var.set(request_id)
        start = time.perf_counter()
        status = 500

        async def send_with_request_id(message: Message) -> None:
            """
            Stamp the request id on the response headers and remember the status.
            """
            nonlocal status
            if message["type"] == "http.response.start":
                status = message["status"]
                MutableHeaders(scope=message).append(REQUEST_ID_HEADER, request_id)
            await send(message)

        try:
            await self.app(scope, receive, send_with_request_id)
        finally:
            elapsed = time.perf_counter() - start
            method = scope["method"] if scope["method"] in _KNOWN_METHODS else "OTHER"
            route = _route_label(scope)
            HTTP_REQUESTS.labels(method=method, route=route, status=str(status)).inc()
            HTTP_REQUEST_DURATION.labels(method=method, route=route).observe(elapsed)
            path = scope["path"]
            if not _is_quiet(path):
                logger.info(
                    "%s %s %d %.1f ms",
                    method,
                    log_safe(path, max_len=200),
                    status,
                    elapsed * 1000,
                )
            request_id_var.reset(token)
