# Stage 1: Build React frontend
FROM node:20-alpine AS frontend-builder

WORKDIR /app/frontend

# Copy package files first for better caching
COPY app/frontend/package.json app/frontend/package-lock.json* ./

# Install all dependencies (including devDependencies needed for build)
RUN npm ci

# Copy source and build
COPY app/frontend/ ./
RUN npm run build


# Stage 2: Python runtime with FastAPI
FROM python:3.13-slim AS hedge-fund-tracker

# Set environment variables
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements from Pipfile.lock (extract package list)
# First, copy Pipfile to parse dependencies
COPY Pipfile Pipfile.lock ./

# Install pipenv and dependencies
RUN pip install --no-cache-dir pipenv && \
    pipenv install --system --deploy --skip-lock

# Copy application code
COPY app/ ./app/
COPY database/ ./database/

# Create cache directories (populated at runtime via volume mounts)
RUN mkdir -p __llmcache__ __reports__

# Copy built frontend from builder stage
COPY --from=frontend-builder /app/frontend/dist ./app/frontend/dist

# Create non-root user for security
RUN useradd --create-home --shell /bin/bash hedgefund && \
    chown -R hedgefund:hedgefund /app
USER hedgefund

# Expose port
EXPOSE 8000

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/health')" || exit 1

# Run the application
CMD ["python", "-m", "app.main"]
