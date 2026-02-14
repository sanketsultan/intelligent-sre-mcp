#!/usr/bin/env bash
set -euo pipefail

export API_URL="${API_URL:-http://localhost:30080}"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
export PYTHONPATH="$SCRIPT_DIR/src"

PYTHON_BIN="$SCRIPT_DIR/.venv/bin/python"
if [[ -x "$PYTHON_BIN" ]]; then
	exec "$PYTHON_BIN" -m intelligent_sre_mcp.api_client
fi

exec python3 -m intelligent_sre_mcp.api_client
