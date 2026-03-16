#!/usr/bin/env bash
# setup.sh — deploy the full stack to a running Kubernetes cluster.
# Requires: docker, kubectl (with an accessible cluster context)
# For Docker Compose local setup (no K8s), run: ./scripts/quickstart.sh dev

set -euo pipefail

info()    { echo "==> $1"; }
success() { echo "OK  $1"; }
warn()    { echo "WARN $1"; }
error()   { echo "ERR $1" >&2; }

command_exists() { command -v "$1" >/dev/null 2>&1; }

# Find Python 3.10+ (required by this package)
find_python() {
  for cmd in python3.13 python3.12 python3.11 python3.10; do
    if command_exists "$cmd"; then
      echo "$cmd"
      return 0
    fi
  done
  # Fall back to python3 and check version
  if command_exists python3; then
    local ver
    ver=$(python3 -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')" 2>/dev/null)
    local major minor
    major=$(echo "$ver" | cut -d. -f1)
    minor=$(echo "$ver" | cut -d. -f2)
    if [ "$major" -ge 3 ] && [ "$minor" -ge 10 ]; then
      echo "python3"
      return 0
    fi
  fi
  error "Python 3.10+ is required. Install python3.10, 3.11, 3.12, or 3.13."
  return 1
}

wait_for_pods() {
  local namespace=$1
  local max_wait=300
  local elapsed=0
  info "Waiting for pods to be ready in namespace: $namespace"
  while [ $elapsed -lt $max_wait ]; do
    local not_ready
    not_ready=$(kubectl get pods -n "$namespace" --no-headers 2>/dev/null \
      | grep -vc "Running\|Completed" || true)
    if [ "$not_ready" -eq 0 ]; then
      success "All pods ready"
      return 0
    fi
    echo -n "."
    sleep 5
    elapsed=$((elapsed + 5))
  done
  echo ""
  error "Timed out waiting for pods"
  kubectl get pods -n "$namespace"
  return 1
}

PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$PROJECT_DIR"

echo ""
echo "Intelligent SRE MCP — Kubernetes Setup"
echo "======================================="
echo ""

# --- Prerequisites ---
info "Checking prerequisites"
for cmd in kubectl docker; do
  if ! command_exists "$cmd"; then
    error "$cmd is required but not installed"
    exit 1
  fi
  success "$cmd found"
done
PYTHON_CMD=$(find_python) || exit 1
success "$PYTHON_CMD found ($($PYTHON_CMD --version 2>&1))"

if ! kubectl cluster-info >/dev/null 2>&1; then
  error "Cannot reach Kubernetes cluster. Ensure kubectl is configured and the cluster is running."
  exit 1
fi
success "Kubernetes cluster reachable"
echo ""

# --- Ensure namespace exists ---
info "Step 1/6: Ensuring namespace exists"
kubectl apply -f "$PROJECT_DIR/k8s/base/namespace.yaml"
success "Namespace intelligent-sre ready"
echo ""

# --- Create Anthropic API key secret ---
info "Step 2/6: Creating anthropic-credentials secret"
# Load .env to get ANTHROPIC_API_KEY (disable nounset for ${VAR:-default} expressions)
set +u
if [ -f ".env" ]; then
  # shellcheck source=/dev/null
  set -o allexport; source .env; set +o allexport
fi
set -u
if [ -z "${ANTHROPIC_API_KEY:-}" ]; then
  warn "ANTHROPIC_API_KEY not set — skipping secret creation. Set it in .env to enable the webhook agent."
else
  kubectl create secret generic anthropic-credentials \
    --namespace intelligent-sre \
    --from-literal=ANTHROPIC_API_KEY="${ANTHROPIC_API_KEY}" \
    --dry-run=client -o yaml | kubectl apply -f -
  success "anthropic-credentials secret applied"
fi
echo ""

# --- Clean up legacy static PV and broken postgres state ---
info "Step 3/6: Cleaning up stale resources"
# Remove the old manually-managed postgres-pv if it still exists (replaced by dynamic provisioning)
if kubectl get pv postgres-pv >/dev/null 2>&1; then
  warn "Found legacy static PV postgres-pv — removing"
  kubectl delete statefulset postgres -n intelligent-sre --ignore-not-found
  kubectl delete pvc postgres-data-postgres-0 -n intelligent-sre --ignore-not-found
  kubectl delete pv postgres-pv --ignore-not-found
  success "Legacy PV and dependent resources removed"
else
  # Check if postgres pod is in a crash/error state and clean it up
  POSTGRES_PHASE=$(kubectl get pod postgres-0 -n intelligent-sre \
    -o jsonpath='{.status.phase}' 2>/dev/null || true)
  RESTART_COUNT=$(kubectl get pod postgres-0 -n intelligent-sre \
    -o jsonpath='{.status.containerStatuses[0].restartCount}' 2>/dev/null || echo "0")
  if [ "${POSTGRES_PHASE}" = "Failed" ] || [ "${RESTART_COUNT:-0}" -gt 5 ]; then
    warn "Postgres pod is unhealthy (phase=${POSTGRES_PHASE} restarts=${RESTART_COUNT}) — recreating"
    kubectl delete statefulset postgres -n intelligent-sre --ignore-not-found
    kubectl delete pvc postgres-data-postgres-0 -n intelligent-sre --ignore-not-found
    success "Stale postgres resources removed"
  else
    success "No stale resources found"
  fi
fi
echo ""

# --- Build Docker image ---
info "Step 4/6: Building Docker image"
docker build -t intelligent-sre-agent:latest . >/dev/null 2>&1
success "Docker image built: intelligent-sre-agent:latest"
echo ""

# --- Deploy to Kubernetes ---
info "Step 5/6: Deploying to Kubernetes (dev overlay)"
kubectl apply -k k8s/overlays/dev
success "Kustomize resources applied"
echo ""

# --- Wait for pods ---
info "Step 6/6: Verifying deployment"
wait_for_pods "intelligent-sre"
echo ""

# --- Verify service endpoints ---
info "Checking service endpoints"
for url_label in \
  "http://localhost:30080/health|API" \
  "http://localhost:30090/-/healthy|Prometheus" \
  "http://localhost:30300/api/health|Grafana" \
  "http://localhost:30093/-/healthy|Alertmanager"; do
  url="${url_label%%|*}"
  label="${url_label##*|}"
  if curl -sf "$url" >/dev/null 2>&1; then
    success "$label accessible at ${url%%/*}//${url#*//}"
  else
    warn "$label not yet ready at ${url%%/*}//${url#*//} (may need a moment)"
  fi
done
echo ""

# --- Python venv ---
info "Setting up Python virtual environment"
if [ ! -d ".venv" ]; then
  "$PYTHON_CMD" -m venv .venv
  .venv/bin/python -m pip install -q --upgrade pip setuptools wheel
  .venv/bin/python -m pip install -q -r requirements.txt
  # Use non-editable install: Homebrew Python 3.12 skips __editable__.*.pth files
  .venv/bin/python -m pip install -q .
  success "Virtual environment created at .venv/ ($("$PYTHON_CMD" --version 2>&1))"
else
  # Recreate if the venv Python is too old (< 3.10)
  venv_minor=$(.venv/bin/python -c "import sys; print(sys.version_info.minor)" 2>/dev/null || echo "0")
  venv_major=$(.venv/bin/python -c "import sys; print(sys.version_info.major)" 2>/dev/null || echo "0")
  if [ "$venv_major" -lt 3 ] || { [ "$venv_major" -eq 3 ] && [ "$venv_minor" -lt 10 ]; }; then
    warn "Existing venv uses Python $venv_major.$venv_minor (need 3.10+). Recreating..."
    "$PYTHON_CMD" -m venv --clear .venv
    .venv/bin/python -m pip install -q --upgrade pip setuptools wheel
    .venv/bin/python -m pip install -q -r requirements.txt
    .venv/bin/python -m pip install -q .
    success "Virtual environment recreated with $PYTHON_CMD"
  elif ! .venv/bin/python -c "import intelligent_sre_agent" 2>/dev/null; then
    .venv/bin/python -m pip install -q .
    success "Package installed into existing venv"
  else
    success "Virtual environment already up to date at .venv/"
  fi
fi
echo ""

echo "Setup complete."
echo ""
echo "  API:         http://localhost:30080"
echo "  Prometheus:  http://localhost:30090"
echo "  Grafana:     http://localhost:30300  (see .env for credentials)"
echo "  Alertmanager:http://localhost:30093"
echo ""
echo "Next steps:"
echo "  - Set ANTHROPIC_API_KEY in .env to use the SRE agent"
echo "  - Run: source .venv/bin/activate && python -m intelligent_sre_agent.sre_agent 'health check'"
echo "  - To stop: kubectl delete -k k8s/overlays/dev"
echo ""
