# syntax=docker/dockerfile:1
# Pin to a specific patch so builds are reproducible
FROM python:3.10.17-slim-bookworm AS base

# Prevent .pyc files and enable stdout/stderr streaming
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONPATH=/app/src

WORKDIR /app

# Install OS-level runtime deps, then clean apt cache
RUN apt-get update && apt-get install -y --no-install-recommends \
      libpq5 \
    && rm -rf /var/lib/apt/lists/*

# ---- dependency stage -------------------------------------------------------
FROM base AS deps

COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade pip \
    && pip install --no-cache-dir -r requirements.txt

# ---- final stage ------------------------------------------------------------
FROM base AS final

# Copy installed packages from deps stage (keeps final image lean)
COPY --from=deps /usr/local/lib/python3.10/site-packages /usr/local/lib/python3.10/site-packages
COPY --from=deps /usr/local/bin /usr/local/bin

# Create a non-root user (uid 1000) before copying code
RUN groupadd --gid 1000 appuser \
    && useradd --uid 1000 --gid 1000 --no-create-home appuser

COPY src/ ./src/
COPY pyproject.toml ./

# Install the package itself (non-editable for production)
RUN pip install --no-cache-dir --no-deps .

# Drop to non-root
USER appuser

# Runtime environment defaults (override via K8s ConfigMap / docker-compose env)
ENV PROMETHEUS_URL=http://prometheus:9090 \
    OTLP_ENDPOINT=http://otel-collector:4317 \
    REQUEST_TIMEOUT=10 \
    ENABLE_TRACING=false

EXPOSE 8080

# Real health check – hits the /health endpoint
HEALTHCHECK --interval=30s --timeout=5s --start-period=15s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8080/health')" \
    || exit 1

CMD ["python", "-m", "intelligent_sre_agent.api_server"]
