#!/usr/bin/env bash
set -euo pipefail

export PROMETHEUS_URL="${PROMETHEUS_URL:-http://localhost:9090}"
export USER_NAME="$(whoami)"
export PYTHONPATH="/Users/${USER_NAME}/Desktop/intelligent-sre-mcp/src"

exec "/Users/${USER_NAME}/Desktop/intelligent-sre-mcp/.venv/bin/python" -m intelligent_sre_mcp.server
