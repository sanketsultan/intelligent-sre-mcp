#!/usr/bin/env bash
set -euo pipefail

export API_URL="${API_URL:-http://localhost:30080}"
export USER_NAME="$(whoami)"
export PYTHONPATH="/Users/${USER_NAME}/Desktop/intelligent-sre-mcp/src"

exec "/Users/${USER_NAME}/Desktop/intelligent-sre-mcp/.venv/bin/python" -m intelligent_sre_mcp.api_client
