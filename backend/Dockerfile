# ─────────────────────────────────────────────────────
# API-Pulse Backend — Production Dockerfile
# Build context: repository root
# Usage: docker build -f backend/Dockerfile .
# ─────────────────────────────────────────────────────
FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONPATH=/app

WORKDIR /app

# System libraries required for asyncpg compilation
RUN apt-get update && apt-get install -y --no-install-recommends \
        gcc \
        libpq-dev \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements first for Docker layer caching
COPY backend/requirements.txt .
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# Copy backend source code
COPY backend/ .

# Create a non-root user for security
RUN addgroup --system appgroup && \
    adduser  --system --ingroup appgroup --no-create-home appuser && \
    mkdir -p /app/ml/models && \
    chown -R appuser:appgroup /app/ml/models

USER appuser

EXPOSE 8080

HEALTHCHECK --interval=30s --timeout=10s --start-period=60s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8080/health')" || exit 1

# Shell form so $PORT is expanded at runtime (Render injects PORT automatically)
CMD uvicorn main:app --host 0.0.0.0 --port ${PORT:-8080} --workers 1
