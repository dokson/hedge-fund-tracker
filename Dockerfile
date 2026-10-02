# syntax=docker/dockerfile:1

# Images are written out in every FROM (no ARG): Dependabot only updates literal
# references, bumping tag and digest together.

# ── Stage 1: React frontend ────────────────────────────────────────────────
FROM node:26.10.0-slim@sha256:ec7758ee051e457b468b32bde57b0879010b325bb9862718e9615225ce4aaae1 AS frontend-build
WORKDIR /app/frontend
RUN --mount=type=bind,source=app/frontend/package.json,target=package.json \
    --mount=type=bind,source=app/frontend/package-lock.json,target=package-lock.json \
    --mount=type=cache,target=/root/.npm \
    npm ci --no-audit --fund=false
COPY app/frontend/ ./
RUN npm run build

# ── Stage 2: Python dependencies ───────────────────────────────────────────
# Toolchain stays in this stage, out of the runtime image.
FROM python:3.15.0rc2-slim@sha256:14684656c0069b49e897c63d52bbbe7df8a4bf189911a597403fd3b4ffeaae06 AS python-deps
ENV PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PIPENV_VENV_IN_PROJECT=1 \
    PIPENV_NOSPIN=1
RUN --mount=type=cache,target=/var/cache/apt,sharing=locked \
    --mount=type=cache,target=/var/lib/apt,sharing=locked \
    rm -f /etc/apt/apt.conf.d/docker-clean && \
    apt-get update && apt-get install -y --no-install-recommends build-essential
RUN --mount=type=cache,target=/root/.cache/pip \
    pip install pipenv==2026.0.3
WORKDIR /app
RUN --mount=type=bind,source=Pipfile,target=Pipfile \
    --mount=type=bind,source=Pipfile.lock,target=Pipfile.lock \
    --mount=type=cache,target=/root/.cache/pip \
    pipenv sync

# ── Stage 3: runtime ───────────────────────────────────────────────────────
FROM python:3.15.0rc2-slim@sha256:14684656c0069b49e897c63d52bbbe7df8a4bf189911a597403fd3b4ffeaae06 AS runtime

LABEL org.opencontainers.image.title="Hedge Fund Tracker" \
      org.opencontainers.image.description="SEC 13F, 13D/G and Form 4 tracker with AI-assisted stock analysis" \
      org.opencontainers.image.source="https://github.com/dokson/hedge-fund-tracker" \
      org.opencontainers.image.url="https://github.com/dokson/hedge-fund-tracker" \
      org.opencontainers.image.licenses="LicenseRef-Proprietary"

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PATH="/app/.venv/bin:${PATH}" \
    PORT=8000 \
    HOST=0.0.0.0

RUN groupadd --system --gid 1001 hedgefund && \
    useradd --system --uid 1001 --gid 1001 --create-home --shell /usr/sbin/nologin hedgefund

WORKDIR /app

# Code stays root-owned; only /app (for .env) and data dirs are writable.
RUN mkdir -p __llmcache__ __reports__ __pricecache__ database && \
    chown 1001:1001 /app __llmcache__ __reports__ __pricecache__ database

COPY --link --from=python-deps /app/.venv /app/.venv
COPY --link app/ ./app/
COPY --link alembic.ini ./
# Outside the mounted volume, so the entrypoint can seed a fresh one.
COPY --link database/ ./database-seed/
COPY --link --from=frontend-build /app/frontend/dist ./app/frontend/dist
COPY --link --chmod=755 entrypoint.sh ./

USER 1001:1001

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=10s --start-period=20s --retries=3 \
    CMD ["python", "-c", "import os, urllib.request; urllib.request.urlopen(f'http://localhost:{os.environ[\"PORT\"]}/health', timeout=5)"]

ENTRYPOINT ["./entrypoint.sh"]
CMD ["python", "-m", "app.main"]
