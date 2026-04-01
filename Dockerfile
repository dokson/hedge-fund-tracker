# Stage 1: Build React frontend
FROM node:22-slim AS frontend-build
WORKDIR /app/frontend
COPY app/frontend/package.json app/frontend/package-lock.json ./
RUN npm ci
COPY app/frontend/ ./
RUN npm run build

# Stage 2: Python runtime with FastAPI
FROM python:3.13-slim

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

ENV PORT=8000
EXPOSE ${PORT}

HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/health')" || exit 1

ENTRYPOINT ["./entrypoint.sh"]
CMD ["python", "-m", "app.main"]
