# ─────────────────────────────────────────────────────
# API-Pulse Backend — Production Dockerfile
# ─────────────────────────────────────────────────────
FROM python:3.11-slim

# Prevent .pyc files and enable unbuffered stdout/stderr
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONPATH=/app

WORKDIR /app

# Install only the system libraries required at runtime
# gcc + libpq-dev are needed for asyncpg / psycopg2 compilation
RUN apt-get update && apt-get install -y --no-install-recommends \
        gcc \
        libpq-dev \
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies before copying source
# (Docker layer cache: only re-runs when requirements.txt changes)
COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# Copy application source
COPY . .

# Create a non-root user for security best practice
RUN addgroup --system appgroup && \
    adduser  --system --ingroup appgroup --no-create-home appuser && \
    # Ensure the ML models directory is writable by appuser
    mkdir -p /app/ml/models && \
    chown -R appuser:appgroup /app/ml/models

USER appuser

# Expose the application port
EXPOSE 8080

# Docker-native health check — hits the /health liveness probe
HEALTHCHECK --interval=30s --timeout=10s --start-period=15s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8080/health')" || exit 1

# Production entrypoint
# --workers 1 is correct here because async FastAPI is already concurrent.
# Increase to --workers 2+ only if you run CPU-bound workloads.
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8080", "--workers", "1"]
