# Stage 1: Build React frontend
FROM node:26-slim AS frontend-build
WORKDIR /app/frontend
# .npmrc must land before `npm ci` so legacy-peer-deps=true is honoured
# (jsx-a11y@6.10 still declares eslint <=^9 as peer; we ship eslint 10).
COPY app/frontend/package.json app/frontend/package-lock.json app/frontend/.npmrc ./
RUN npm ci
COPY app/frontend/ ./
RUN npm run build

# Stage 2: Python runtime with FastAPI
FROM python:3.14-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

# Install system dependencies for compiled Python packages
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies
COPY Pipfile Pipfile.lock ./
RUN pip install --no-cache-dir pipenv && \
    pipenv install --deploy --system

# Copy application code
COPY app/ ./app/

# Alembic config — needed by the entrypoint to apply migrations on boot.
COPY alembic.ini ./

# Seed data: stored separately so the volume mount doesn't hide it
COPY database/ ./database-seed/

# Create runtime directories
RUN mkdir -p __llmcache__ __reports__ database

# Copy built frontend from stage 1
COPY --from=frontend-build /app/frontend/dist ./app/frontend/dist

# Entrypoint script to seed the volume on first deploy
COPY entrypoint.sh ./
RUN chmod +x entrypoint.sh

# Create non-root user for security
RUN useradd --create-home --shell /bin/bash hedgefund && \
    chown -R hedgefund:hedgefund /app
USER hedgefund

ENV PORT=8000 \
    HOST=0.0.0.0
EXPOSE ${PORT}

HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD python -c "import os, urllib.request; urllib.request.urlopen(f'http://localhost:{os.environ[\"PORT\"]}/health')" || exit 1

ENTRYPOINT ["./entrypoint.sh"]
CMD ["python", "-m", "app.main"]
