#!/usr/bin/env bash
set -euo pipefail

export PROMETHEUS_URL="${PROMETHEUS_URL:-http://localhost:9090}"
export PYTHONPATH="/Users/sanket/Desktop/intelligent-sre-mcp/src"

exec "/Users/sanket/Desktop/intelligent-sre-mcp/.venv/bin/python" -m intelligent_sre_mcp.server
