#!/usr/bin/env bash
set -euo pipefail

# Simple, friendly setup wrapper for all users
# Usage: ./setup/quickstart.sh [all|docker|k8s|claude|local]

MODE=${1:-all}
PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

print() {
  echo -e "\033[0;34m==>\033[0m $1"
}

warn() {
  echo -e "\033[1;33m⚠\033[0m $1"
}

success() {
  echo -e "\033[0;32m✓\033[0m $1"
}

case "$MODE" in
  all)
    print "Running full setup (K8s + Claude config)"
    "$PROJECT_DIR/setup/setup.sh"
    if [[ "$OSTYPE" == "darwin"* ]] && command -v open >/dev/null 2>&1; then
      if [[ -f "$PROJECT_DIR/setup/restart-claude.sh" ]]; then
        print "Restarting Claude Desktop"
        "$PROJECT_DIR/setup/restart-claude.sh" || warn "Claude restart script failed; please restart manually"
      else
        warn "restart-claude.sh not found; restart Claude Desktop manually"
      fi
    else
      warn "Non-macOS detected; restart Claude Desktop manually"
    fi
    success "All done"
    ;;

  k8s)
    print "Running Kubernetes setup only"
    "$PROJECT_DIR/setup/setup.sh"
    success "Kubernetes setup complete"
    ;;

  claude)
    print "Configuring Claude Desktop only"
    "$PROJECT_DIR/setup/setup_claude.sh"
    success "Claude Desktop configuration complete"
    ;;

  local)
    print "Setting up local Python environment"
    if [[ ! -d "$PROJECT_DIR/.venv" ]]; then
      python3 -m venv "$PROJECT_DIR/.venv"
    fi
    "$PROJECT_DIR/.venv/bin/python" -m pip install --upgrade pip setuptools wheel
    "$PROJECT_DIR/.venv/bin/python" -m pip install -r "$PROJECT_DIR/requirements.txt"
    success "Local environment ready"
    ;;

  docker)
    print "Running public Docker image"
    echo ""
    echo "docker pull sanketsultan/intelligent-sre-mcp:latest"
    echo "docker run --rm -p 30080:8080 sanketsultan/intelligent-sre-mcp:latest"
    echo ""
    ;;

  *)
    echo "Usage: $0 [all|docker|k8s|claude|local]"
    exit 1
    ;;
esac
