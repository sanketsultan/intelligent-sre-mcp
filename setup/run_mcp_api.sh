#!/usr/bin/env bash
set -euo pipefail

export API_URL="${API_URL:-http://localhost:30080}"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
export PYTHONPATH="$PROJECT_DIR/src"

PYTHON_BIN="$PROJECT_DIR/.venv/bin/python"
if [[ -x "$PYTHON_BIN" ]]; then
	exec "$PYTHON_BIN" -m intelligent_sre_mcp.api_client
fi

exec python3 -m intelligent_sre_mcp.api_client
