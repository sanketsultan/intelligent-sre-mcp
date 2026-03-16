#!/usr/bin/env bash
# run-slack-bot.sh — Start the SRE Slack bot (Socket Mode)
#
# Usage:
#   ./scripts/run-slack-bot.sh
#
# Required environment variables (can be set in .env):
#   SLACK_BOT_TOKEN     — Bot User OAuth Token (xoxb-...)
#   SLACK_APP_TOKEN     — App-Level Token for Socket Mode (xapp-...)
#   ANTHROPIC_API_KEY   — Anthropic API key
#
# Optional:
#   API_URL             — intelligent-sre-agent API base URL (default: http://localhost:30080)
#   ALERTMANAGER_URL    — Alertmanager URL (default: http://localhost:9093)
#   SLACK_CHANNEL       — default channel for alert notifications
#   GITHUB_TOKEN        — GitHub token for post-mortem issue creation
#   GITHUB_REPO         — GitHub repo (owner/repo) for post-mortem issues

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"

# Load .env if present
if [[ -f "${REPO_ROOT}/.env" ]]; then
  echo "[run-slack-bot] Loading .env ..."
  set -o allexport
  # shellcheck source=/dev/null
  source "${REPO_ROOT}/.env"
  set +o allexport
fi

# Validate required environment variables
if [[ -z "${SLACK_BOT_TOKEN:-}" ]]; then
  echo "Error: SLACK_BOT_TOKEN is not set."
  echo "  Get a token at https://api.slack.com/apps"
  echo "  Then set it in .env or export it before running this script."
  exit 1
fi

if [[ -z "${SLACK_APP_TOKEN:-}" ]]; then
  echo "Error: SLACK_APP_TOKEN is not set."
  echo "  Enable Socket Mode in your Slack app and generate an App-Level Token."
  echo "  Then set it in .env or export it before running this script."
  exit 1
fi

if [[ -z "${ANTHROPIC_API_KEY:-}" ]]; then
  echo "Error: ANTHROPIC_API_KEY is not set."
  exit 1
fi

# Activate virtualenv if present
if [[ -f "${REPO_ROOT}/.venv/bin/activate" ]]; then
  echo "[run-slack-bot] Activating .venv ..."
  # shellcheck source=/dev/null
  source "${REPO_ROOT}/.venv/bin/activate"
fi

echo "[run-slack-bot] Starting SRE Slack bot ..."
echo "  API_URL          = ${API_URL:-http://localhost:30080}"
echo "  ALERTMANAGER_URL = ${ALERTMANAGER_URL:-http://localhost:9093}"
echo "  SLACK_CHANNEL    = ${SLACK_CHANNEL:-(not set)}"
echo "  GITHUB_REPO      = ${GITHUB_REPO:-(not set)}"

exec python -m intelligent_sre_agent.bot.slack_bot "$@"
