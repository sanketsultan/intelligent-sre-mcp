#!/usr/bin/env bash
# run-discord-bot.sh — Start the SRE Discord bot
#
# Usage:
#   ./scripts/run-discord-bot.sh
#
# Required environment variables (can be set in .env):
#   DISCORD_BOT_TOKEN   — Discord bot token
#   ANTHROPIC_API_KEY   — Anthropic API key
#
# Optional:
#   API_URL             — intelligent-sre-mcp API base URL (default: http://localhost:30080)
#   ALERTMANAGER_URL    — Alertmanager URL (default: http://localhost:9093)
#   GITHUB_TOKEN        — GitHub token for post-mortem issue creation
#   GITHUB_REPO         — GitHub repo (owner/repo) for post-mortem issues

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"

# Load .env if present
if [[ -f "${REPO_ROOT}/.env" ]]; then
  echo "[run-discord-bot] Loading .env ..."
  set -o allexport
  # shellcheck source=/dev/null
  source "${REPO_ROOT}/.env"
  set +o allexport
fi

# Validate required environment variables
if [[ -z "${DISCORD_BOT_TOKEN:-}" ]]; then
  echo "Error: DISCORD_BOT_TOKEN is not set."
  echo "  Get a token at https://discord.com/developers/applications"
  echo "  Then set it in .env or export it before running this script."
  exit 1
fi

if [[ -z "${ANTHROPIC_API_KEY:-}" ]]; then
  echo "Error: ANTHROPIC_API_KEY is not set."
  exit 1
fi

# Activate virtualenv if present
if [[ -f "${REPO_ROOT}/.venv/bin/activate" ]]; then
  echo "[run-discord-bot] Activating .venv ..."
  # shellcheck source=/dev/null
  source "${REPO_ROOT}/.venv/bin/activate"
fi

echo "[run-discord-bot] Starting SRE Discord bot ..."
echo "  API_URL          = ${API_URL:-http://localhost:30080}"
echo "  ALERTMANAGER_URL = ${ALERTMANAGER_URL:-http://localhost:9093}"
echo "  GITHUB_REPO      = ${GITHUB_REPO:-(not set)}"

exec python -m intelligent_sre_mcp.bot.discord_bot "$@"
