# Use Python 3.10+ as base image
FROM python:3.10-slim

# Set working directory
WORKDIR /app

# Copy source code first
COPY src/ ./src/
COPY requirements.txt pyproject.toml ./

# Install dependencies
RUN pip install --no-cache-dir -r requirements.txt && \
    pip install --no-cache-dir -e .

# Set environment variables
ENV PROMETHEUS_URL=http://prometheus:9090
ENV OTLP_ENDPOINT=http://otel-collector:4317
ENV REQUEST_TIMEOUT=10
ENV PYTHONPATH=/app/src

# Expose port
EXPOSE 8080

# Run the FastAPI server
CMD ["python", "-m", "intelligent_sre_mcp.api_server"]
