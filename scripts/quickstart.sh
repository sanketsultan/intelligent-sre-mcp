#!/usr/bin/env bash
# quickstart.sh — convenience wrapper for common setup modes.
# Usage: ./scripts/quickstart.sh [dev|k8s|local|help]
#   dev    Start full stack via Docker Compose (default, no K8s required)
#   k8s    Deploy to local Kubernetes cluster
#   local  Set up Python virtual environment only
#   help   Show this message

set -euo pipefail

MODE=${1:-dev}
PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

info()    { echo "==> $1"; }
success() { echo "OK  $1"; }
warn()    { echo "WARN $1"; }

case "$MODE" in
  dev)
    info "Starting full stack via Docker Compose"
    if [ ! -f "$PROJECT_DIR/.env" ]; then
      cp "$PROJECT_DIR/.env.example" "$PROJECT_DIR/.env"
      warn ".env created from .env.example — set ANTHROPIC_API_KEY before using the SRE agent"
    fi
    cd "$PROJECT_DIR"
    docker compose up -d
    success "Stack is up"
    echo ""
    echo "  API:        http://localhost:8080/health"
    echo "  Prometheus: http://localhost:9090"
    echo "  Grafana:    http://localhost:3000"
    echo ""
    echo "To stop: docker compose down"
    ;;

  k8s)
    info "Deploying to Kubernetes (dev overlay)"
    "$PROJECT_DIR/scripts/setup.sh"
    success "Kubernetes setup complete"
    ;;

  local)
    info "Setting up local Python environment"
    if [ ! -d "$PROJECT_DIR/.venv" ]; then
      python3 -m venv "$PROJECT_DIR/.venv"
    fi
    "$PROJECT_DIR/.venv/bin/python" -m pip install --upgrade pip setuptools wheel
    "$PROJECT_DIR/.venv/bin/python" -m pip install -r "$PROJECT_DIR/requirements.txt"
    success "Virtual environment ready at .venv/"
    echo "Activate with: source .venv/bin/activate"
    ;;

  help|--help|-h)
    echo "Usage: ./scripts/quickstart.sh [dev|k8s|local|help]"
    echo ""
    echo "  dev    Start full stack via Docker Compose (default, no K8s required)"
    echo "  k8s    Deploy to local Kubernetes cluster"
    echo "  local  Set up Python virtual environment only"
    echo "  help   Show this message"
    ;;

  *)
    echo "Unknown mode: $MODE" >&2
    echo "Usage: ./scripts/quickstart.sh [dev|k8s|local|help]" >&2
    exit 1
    ;;
esac
