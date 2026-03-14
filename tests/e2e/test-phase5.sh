#!/usr/bin/env bash
set -euo pipefail

API_URL="http://localhost:30080"
NAMESPACE="intelligent-sre"

color() { printf "\033[0;%sm%s\033[0m" "$1" "$2"; }
info() { echo "$(color 34 "==>") $1"; }
success() { echo "$(color 32 "✓") $1"; }
warn() { echo "$(color 33 "⚠") $1"; }

info "Phase 5 validation: learning endpoints + optional real action"

info "Checking API health"
if ! curl -s "$API_URL/health" >/dev/null; then
  echo "API not reachable at $API_URL"
  exit 1
fi
success "API reachable"

echo ""
info "Fetching current action stats"
curl -s "$API_URL/learning/action-stats?hours=24" | jq

echo ""
info "Fetching recurring issues"
curl -s "$API_URL/learning/recurring-issues?hours=24&min_count=2" | jq

echo ""
read -r -p "Run a real healing action to generate an action_id? (y/N): " CONFIRM
if [[ ! "$CONFIRM" =~ ^[Yy]$ ]]; then
  warn "Skipping real action. Phase 5 endpoints validated."
  exit 0
fi

info "Selecting a running pod in $NAMESPACE"
POD_NAME=$(kubectl get pods -n "$NAMESPACE" --field-selector=status.phase=Running -o jsonpath='{.items[0].metadata.name}' 2>/dev/null || true)
if [[ -z "$POD_NAME" ]]; then
  echo "No running pods found in $NAMESPACE"
  exit 1
fi
success "Selected pod: $POD_NAME"

echo ""
info "Restarting pod (real action)"
ACTION_RESPONSE=$(curl -s -X POST "$API_URL/healing/restart-pod?namespace=$NAMESPACE&pod_name=$POD_NAME&dry_run=false")
echo "$ACTION_RESPONSE" | jq

ACTION_ID=$(echo "$ACTION_RESPONSE" | jq -r '.action_id // empty')
if [[ -z "$ACTION_ID" ]]; then
  warn "No action_id returned. Cannot record outcome."
  exit 0
fi

sleep 2
info "Recording outcome for action_id=$ACTION_ID"
curl -s -X POST "$API_URL/learning/record-outcome" \
  -H 'Content-Type: application/json' \
  -d "{\"action_id\": $ACTION_ID, \"outcome\": \"success\", \"resolution_time_seconds\": 30, \"notes\": \"phase5 validation\"}" | jq

success "Phase 5 validation complete"
