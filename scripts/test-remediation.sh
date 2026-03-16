#!/usr/bin/env bash
# test-remediation.sh — end-to-end chaos test for the SRE automated remediation pipeline.
#
# What this script does:
#   1. Deploys 4 deliberately broken pods that simulate a cascading incident
#   2. Waits for them to enter failure states
#   3. Prints the "before" state so you can see all the breakage
#   4. POSTs a critical alert to the Alertmanager webhook (triggers the full pipeline)
#   5. Waits for the SRE agent to investigate + remediate in the background
#   6. Prints the "after" state and the agent's investigation/remediation from the DB
#   7. Cleans up all chaos resources
#
# Failure modes simulated (all fixable via patch_deployment, not just scale-to-zero):
#   crash-worker     CrashLoopBackOff   SIMULATE_CRASH=true env var causes exit 1
#                                       Fix: patch env var to false
#   dependent-worker Init:Error         cascading — init container blocked by crash-worker
#                                       Fix: auto-recovers once crash-worker is healthy
#   pending-worker   Pending            impossible nodeSelector (hardware-accelerator=a100-gpu)
#                                       Fix: patch nodeSelector to null
#   sick-api         Running/NotReady   readiness probe targets port 9999 (not listening)
#                                       Fix: patch readinessProbe to null
#
# Usage:
#   export ANTHROPIC_API_KEY=sk-ant-...
#   ./scripts/test-remediation.sh
#
#   # Skip cleanup to inspect results manually:
#   SKIP_CLEANUP=1 ./scripts/test-remediation.sh

set -euo pipefail

# ── Load .env so ANTHROPIC_API_KEY does not need to be exported manually ─────
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(dirname "$SCRIPT_DIR")"
if [[ -f "${REPO_ROOT}/.env" ]]; then
  set +u            # .env may use ${VAR:-default} before vars are defined
  set -o allexport
  # shellcheck source=/dev/null
  source "${REPO_ROOT}/.env"
  set +o allexport
  set -u
fi

API_URL="${API_URL:-http://localhost:30080}"
NAMESPACE="intelligent-sre"
CHAOS_LABEL="chaos-test=true"
WAIT_FOR_FAILURES="${WAIT_FOR_FAILURES:-50}"  # seconds to wait for pods to fail
WAIT_FOR_AGENT="${WAIT_FOR_AGENT:-300}"        # seconds for agent to investigate+remediate
SKIP_CLEANUP="${SKIP_CLEANUP:-0}"

info()    { echo ""; echo "==> $*"; }
success() { echo "OK  $*"; }
warn()    { echo "WARN $*"; }
sep()     { echo ""; echo "------------------------------------------------------------------------"; }

# ---------------------------------------------------------------------------
# 0. Preconditions
# ---------------------------------------------------------------------------
info "Checking prerequisites"

if [[ -z "${ANTHROPIC_API_KEY:-}" ]]; then
  echo "Error: ANTHROPIC_API_KEY is not set." >&2
  echo "  Add it to .env: echo 'ANTHROPIC_API_KEY=sk-ant-...' >> .env" >&2
  exit 1
fi
success "ANTHROPIC_API_KEY set"

if ! curl -sf "${API_URL}/health" >/dev/null; then
  echo "Error: SRE API not reachable at ${API_URL}" >&2
  echo "  Make sure 'kubectl apply -k k8s/overlays/dev' has been run." >&2
  exit 1
fi
success "SRE API reachable at ${API_URL}"

if ! kubectl get namespace "${NAMESPACE}" >/dev/null 2>&1; then
  echo "Error: namespace ${NAMESPACE} does not exist." >&2
  exit 1
fi
success "Namespace ${NAMESPACE} exists"

# ---------------------------------------------------------------------------
# 1. Deploy chaos workloads
# ---------------------------------------------------------------------------
sep
info "Step 1/6: Deploying chaos workloads"
kubectl apply -k k8s/chaos/
echo ""
echo "Chaos deployments created:"
kubectl get deployments -n "${NAMESPACE}" -l "${CHAOS_LABEL}" 2>/dev/null || true

# ---------------------------------------------------------------------------
# 2. Wait for pods to enter failure states
# ---------------------------------------------------------------------------
sep
info "Step 2/6: Waiting ${WAIT_FOR_FAILURES}s for pods to enter failure states..."
echo "(crash-worker needs ~10s to CrashLoop, pending-worker is immediate)"
sleep "${WAIT_FOR_FAILURES}"

# ---------------------------------------------------------------------------
# 3. Show BEFORE state — all the breakage
# ---------------------------------------------------------------------------
sep
info "Step 3/6: System state BEFORE remediation"
echo ""
echo "Chaos pods:"
kubectl get pods -n "${NAMESPACE}" -l "${CHAOS_LABEL}" \
  -o custom-columns='NAME:.metadata.name,STATUS:.status.phase,READY:.status.containerStatuses[0].ready,RESTARTS:.status.containerStatuses[0].restartCount,REASON:.status.containerStatuses[0].state.waiting.reason' \
  2>/dev/null || kubectl get pods -n "${NAMESPACE}" -l "${CHAOS_LABEL}"

echo ""
echo "All pods in namespace (health overview):"
kubectl get pods -n "${NAMESPACE}"

echo ""
echo "Relevant K8s events:"
kubectl get events -n "${NAMESPACE}" \
  --field-selector reason=BackOff,reason=Failed,reason=FailedScheduling \
  --sort-by='.lastTimestamp' 2>/dev/null | tail -20 || true

# ---------------------------------------------------------------------------
# 4. Trigger the full automated pipeline via Alertmanager webhook
# ---------------------------------------------------------------------------
sep
info "Step 4/6: Triggering automated remediation via Alertmanager webhook"
echo ""
echo "POSTing critical alert to ${API_URL}/alertmanager/webhook..."
echo "This triggers: save to DB -> SRE agent investigate -> SRE agent remediate"
echo ""

ALERT_PAYLOAD=$(cat <<EOF
{
  "version": "4",
  "groupKey": "chaos-test-incident",
  "status": "firing",
  "receiver": "intelligent-sre-webhook",
  "alerts": [
    {
      "status": "firing",
      "labels": {
        "alertname": "ChaosTestCascadingFailure",
        "severity": "critical",
        "namespace": "${NAMESPACE}",
        "team": "sre"
      },
      "annotations": {
        "summary": "Cascading pod failures detected in ${NAMESPACE}",
        "description": "Multiple pods are in failure states requiring root-cause fixes (not just scaling to zero): crash-worker is in CrashLoopBackOff because SIMULATE_CRASH env var is set to true — fix by patching the env var to false; dependent-worker is stuck in Init:Error because crash-worker-svc has no ready endpoints (cascading failure — will auto-recover once crash-worker is fixed); pending-worker cannot be scheduled because nodeSelector hardware-accelerator=a100-gpu matches no nodes — fix by patching nodeSelector to null; sick-api is Running but never Ready because its readiness probe targets port 9999 which is not open — fix by patching readinessProbe to null. For each issue use patch_deployment to fix the configuration and make the pod Running and Ready, not just scale to zero."
      },
      "startsAt": "$(date -u +%Y-%m-%dT%H:%M:%SZ)",
      "generatorURL": "http://prometheus:9090/graph"
    }
  ]
}
EOF
)

WEBHOOK_RESPONSE=$(curl -s -X POST "${API_URL}/alertmanager/webhook" \
  -H "Content-Type: application/json" \
  -d "${ALERT_PAYLOAD}")

echo "Webhook response: ${WEBHOOK_RESPONSE}"
ALERT_ID=$(echo "${WEBHOOK_RESPONSE}" | python3 -c "import sys,json; d=json.load(sys.stdin); print(d.get('alert_ids',[None])[0] or d.get('saved_ids',[None])[0] or 'unknown')" 2>/dev/null || echo "unknown")
echo ""
success "Alert saved (id=${ALERT_ID}). Agent is running in the background..."

# ---------------------------------------------------------------------------
# 5. Wait for agent to complete investigation + remediation
# ---------------------------------------------------------------------------
sep
info "Step 5/6: Waiting ${WAIT_FOR_AGENT}s for SRE agent to investigate and remediate..."
echo "(The agent runs two passes: Phase 1 investigation, then Phase 2 remediation)"
echo ""

ELAPSED=0
INTERVAL=15
while [ "${ELAPSED}" -lt "${WAIT_FOR_AGENT}" ]; do
  printf "  [%3ds] Pod status: " "${ELAPSED}"
  kubectl get pods -n "${NAMESPACE}" -l "${CHAOS_LABEL}" \
    --no-headers -o custom-columns='X:.metadata.name,Y:.status.phase' 2>/dev/null \
    | tr '\n' '  ' || true
  echo ""
  sleep "${INTERVAL}"
  ELAPSED=$((ELAPSED + INTERVAL))
done

# ---------------------------------------------------------------------------
# 6. Show AFTER state
# ---------------------------------------------------------------------------
sep
info "Step 6/6: System state AFTER remediation"
echo ""
echo "Chaos pods (goal: all Running and Ready, not scaled to zero):"
kubectl get pods -n "${NAMESPACE}" -l "${CHAOS_LABEL}" \
  -o custom-columns='NAME:.metadata.name,STATUS:.status.phase,READY:.status.containerStatuses[0].ready,RESTARTS:.status.containerStatuses[0].restartCount' \
  2>/dev/null || echo "(no chaos pods found)"

echo ""
echo "Deployment readiness (READY should equal DESIRED — not 0/0):"
kubectl get deployments -n "${NAMESPACE}" -l "${CHAOS_LABEL}" \
  -o custom-columns='NAME:.metadata.name,DESIRED:.spec.replicas,READY:.status.readyReplicas,AVAILABLE:.status.availableReplicas' \
  2>/dev/null || true

echo ""
echo "Summary — pass criteria:"
FIXED=0
TOTAL=0
for deploy in crash-worker pending-worker sick-api dependent-worker; do
  TOTAL=$((TOTAL + 1))
  READY=$(kubectl get deployment "${deploy}" -n "${NAMESPACE}" \
    -o jsonpath='{.status.readyReplicas}' 2>/dev/null || echo "0")
  DESIRED=$(kubectl get deployment "${deploy}" -n "${NAMESPACE}" \
    -o jsonpath='{.spec.replicas}' 2>/dev/null || echo "0")
  if [ "${READY:-0}" -gt 0 ] && [ "${DESIRED:-0}" -gt 0 ]; then
    echo "  PASS  ${deploy}: ${READY}/${DESIRED} replicas Ready"
    FIXED=$((FIXED + 1))
  else
    echo "  FAIL  ${deploy}: ${READY:-0}/${DESIRED:-0} replicas Ready"
  fi
done
echo ""
echo "Result: ${FIXED}/${TOTAL} deployments fully remediated (Running and Ready)"

echo ""
echo "All pods in namespace (health overview):"
kubectl get pods -n "${NAMESPACE}"

# ---------------------------------------------------------------------------
# 7. Show agent investigation + remediation from DB
# ---------------------------------------------------------------------------
sep
info "Agent investigation and remediation results from DB"
echo ""

if [ "${ALERT_ID}" != "unknown" ]; then
  echo "Fetching alert ${ALERT_ID}..."
  curl -s "${API_URL}/alerts/${ALERT_ID}" | python3 -m json.tool 2>/dev/null || true
else
  echo "Fetching most recent alert..."
  curl -s "${API_URL}/alerts" | python3 -c "
import sys, json
alerts = json.load(sys.stdin)
if not alerts:
    print('No alerts found in DB')
    sys.exit(0)
latest = alerts[-1]
print(f'Alert #{latest[\"id\"]}: {latest[\"name\"]} ({latest[\"status\"]})')
print()
print('--- Investigation ---')
print(latest.get('investigation') or '(not yet complete)')
print()
print('--- Remediation ---')
print(latest.get('remediation') or '(not yet complete — may still be running)')
" 2>/dev/null || curl -s "${API_URL}/alerts" | python3 -m json.tool | tail -50
fi

# ---------------------------------------------------------------------------
# Cleanup
# ---------------------------------------------------------------------------
sep
if [ "${SKIP_CLEANUP}" = "1" ]; then
  warn "SKIP_CLEANUP=1: chaos resources left in place for manual inspection."
  echo "  To clean up manually: kubectl delete -k k8s/chaos/"
else
  info "Cleaning up chaos resources"
  kubectl delete -k k8s/chaos/ --ignore-not-found=true
  success "Chaos resources removed"
fi

sep
echo ""
echo "Test complete."
echo ""
echo "  Full alert history:  ${API_URL}/alerts"
echo "  Healing action log:  ${API_URL}/healing/action-history?namespace=${NAMESPACE}"
echo ""
