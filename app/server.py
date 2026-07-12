import os

# Fix terminal width for output streamed to the web UI
os.environ.setdefault("COLUMNS", "80")

from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, Request
from fastapi.exceptions import HTTPException as StarletteHTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse, Response
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.middleware import SlowAPIMiddleware
from starlette.middleware.base import BaseHTTPMiddleware

from app.api.admin import router as admin_router
from app.api.ai import router as ai_router
from app.api.api_keys import router as api_keys_router
from app.api.common import limiter
from app.api.data import router as data_router
from app.api.me import router as me_router
from app.api.paths import _FRONTEND_ROOT, _safe_frontend_path
from app.api.settings import router as settings_router

# Importing app.api.sse installs the SSE stdout wrapper (keep on the boot path);
# the names are also re-exported here for the test suite.
from app.api.sse import (  # noqa: F401
    _ContextAwareStdout,
    _request_log_q,
    _run_sse_target,
)
from app.api.starred import router as starred_router
from app.auth import include_routers_for_auth


def _validate_deployment_secrets() -> None:
    """
    In a hardened deployment (secure cookies → HTTPS → real deploy), refuse to
    start with the dev-default token-signing secrets: they would let anyone forge
    verification / password-reset tokens. No effect in local/dev (COOKIE_SECURE
    unset), so the local single-user tool keeps working with the defaults.
    """
    from app.auth.backend import COOKIE_SECURE
    from app.auth.manager import RESET_PASSWORD_TOKEN_SECRET, VERIFICATION_TOKEN_SECRET

    if not COOKIE_SECURE:
        return

    weak = [
        name
        for name, value in (
            ("RESET_PASSWORD_TOKEN_SECRET", RESET_PASSWORD_TOKEN_SECRET),
            ("VERIFICATION_TOKEN_SECRET", VERIFICATION_TOKEN_SECRET),
        )
        if value.startswith("dev-only")
    ]
    if weak:
        raise RuntimeError(
            "COOKIE_SECURE is set (production posture) but dev-default signing secrets "
            f"are still in use: {weak}. Set them via environment variables before deploying."
        )


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
    # Refuse dev-default signing secrets in a production posture (token forgery).
    _validate_deployment_secrets()
    yield
    # Shutdown: dispose the connection pool so pooled sockets close gracefully
    # instead of relying on process exit.
    from app.db.session import engine

    await engine.dispose()


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

    async def dispatch(self, request: Request, call_next) -> Response:
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
            "style-src 'self' 'unsafe-inline' https://fonts.googleapis.com; "
            "img-src 'self' data: https:; "
            "font-src 'self' data: https://fonts.gstatic.com; "
            "connect-src 'self'; "
            "frame-ancestors 'none'; "
            "base-uri 'self'"
        )
        return response


app.add_middleware(SecurityHeadersMiddleware)


# ── Rate limiting ─────────────────────────────────────────────────────────────
# `limiter` is defined in app.api.common so routers can share the one instance.
# The middleware is what applies `default_limits` to every route; without it
# only routes with an explicit @limiter.limit decorator are throttled.
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)  # type: ignore[arg-type]
app.add_middleware(SlowAPIMiddleware)


# ── Routers ─────────────────────────────────────────────────────────────────
# Domain endpoints live in app/api/*; server.py keeps only app wiring, the
# health probe, and SPA/static serving (whose catch-all must be registered last).
include_routers_for_auth(app)
app.include_router(me_router)
app.include_router(api_keys_router)
app.include_router(starred_router)
app.include_router(ai_router)
app.include_router(admin_router)
app.include_router(data_router)
app.include_router(settings_router)


@app.get("/health")
@limiter.exempt
async def health_check() -> dict[str, str]:
    """
    Health check endpoint for Docker and load balancers.
    """
    from app.utils.version import get_version

    return {"status": "healthy", "version": get_version()}


# ── Static frontend ────────────────────────────────────────────────────────────


@app.exception_handler(StarletteHTTPException)
async def http_exception_handler(request: Request, exc: StarletteHTTPException) -> Response:
    # For 404s on non-API routes, serve the SPA index.html (React Router handles routing)
    if exc.status_code == 404 and not request.url.path.startswith(("/api/", "/database/")):
        index = _FRONTEND_ROOT / "index.html"
        if index.exists():
            return FileResponse(str(index))
    return JSONResponse({"detail": exc.detail}, status_code=exc.status_code)


# Exempt from the default rate limit: one SPA page view fans out to many asset
# requests, which must not consume the API budget of real endpoints.
@app.get("/{full_path:path}")
@limiter.exempt
async def serve_spa(full_path: str) -> FileResponse:
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
