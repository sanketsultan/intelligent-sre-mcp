#!/usr/bin/env bash
# run-sre-agent.sh — convenience wrapper for the SRE Incident Response Agent
#
# Usage:
#   ./scripts/run-sre-agent.sh "What is the current health of the system?"
#   ./scripts/run-sre-agent.sh --remediate "Pods are CrashLoopBackOff in production"
#   API_URL=http://my-cluster:30080 ./scripts/run-sre-agent.sh "Check health"
#
# Environment variables:
#   ANTHROPIC_API_KEY  — Required. Anthropic API key.
#   API_URL            — intelligent-sre-mcp API base URL (default: http://localhost:30080)
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(dirname "$SCRIPT_DIR")"

# ── Load .env so ANTHROPIC_API_KEY does not need to be exported manually ─────
if [[ -f "${REPO_ROOT}/.env" ]]; then
  set -o allexport
  # shellcheck source=/dev/null
  source "${REPO_ROOT}/.env"
  set +o allexport
fi

# ── Validate API key ─────────────────────────────────────────────────────────
if [[ -z "${ANTHROPIC_API_KEY:-}" ]]; then
  echo "Error: ANTHROPIC_API_KEY is not set." >&2
  echo "  Add it to .env: echo 'ANTHROPIC_API_KEY=sk-ant-...' >> .env" >&2
  exit 1
fi

# ── Activate virtualenv if present ───────────────────────────────────────────
if [[ -f "${REPO_ROOT}/.venv/bin/activate" ]]; then
  # shellcheck source=/dev/null
  source "${REPO_ROOT}/.venv/bin/activate"
fi

# ── Run the agent ─────────────────────────────────────────────────────────────
exec python -m intelligent_sre_mcp.sre_agent "$@"
