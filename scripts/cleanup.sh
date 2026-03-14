#!/usr/bin/env bash
set -euo pipefail

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Function to print colored output
print_step() {
    echo -e "${BLUE}==>${NC} $1"
}

print_success() {
    echo -e "${GREEN}✓${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}⚠${NC} $1"
}

print_error() {
    echo -e "${RED}✗${NC} $1"
}

# Function to check if a command exists
command_exists() {
    command -v "$1" >/dev/null 2>&1
}

# Banner
echo ""
echo "╔══════════════════════════════════════════════════════╗"
echo "║    Intelligent SRE MCP - Cleanup Script              ║"
echo "╚══════════════════════════════════════════════════════╝"
echo ""

# Check if kubectl is available
if ! command_exists kubectl; then
    print_error "kubectl is not installed. Cannot proceed with cleanup."
    exit 1
fi

# Check if namespace exists
if ! kubectl get namespace intelligent-sre >/dev/null 2>&1; then
    print_warning "Namespace 'intelligent-sre' does not exist. Nothing to clean up."
    exit 0
fi

# Confirmation prompt
echo "This will delete the following:"
echo "  • Kubernetes namespace: intelligent-sre"
echo "  • All pods, services, and deployments in that namespace"
echo "  • Prometheus data"
echo "  • Grafana data"
echo "  • All monitoring components"
echo ""
echo "Docker image 'intelligent-sre-mcp:latest' and Claude Desktop config will NOT be removed."
echo ""
read -p "Are you sure you want to continue? (yes/no): " -r
echo ""

if [[ ! $REPLY =~ ^[Yy][Ee][Ss]$ ]]; then
    print_warning "Cleanup cancelled."
    exit 0
fi

# Get the project directory
PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$PROJECT_DIR"

# Step 1: Delete all Kubernetes resources
print_step "Step 1/3: Removing Kubernetes resources..."

# Delete individual resources first (for cleaner output)
kubectl delete -f k8s/intelligent-sre-mcp.yaml --ignore-not-found=true >/dev/null 2>&1
print_success "Intelligent SRE MCP API removed"

kubectl delete -f k8s/demo-metrics.yaml --ignore-not-found=true >/dev/null 2>&1
print_success "Demo Metrics removed"

kubectl delete -f k8s/jaeger.yaml --ignore-not-found=true >/dev/null 2>&1
print_success "Jaeger removed"

kubectl delete -f k8s/node-exporter.yaml --ignore-not-found=true >/dev/null 2>&1
print_success "Node Exporter removed"

kubectl delete -f k8s/otel-collector.yaml --ignore-not-found=true >/dev/null 2>&1
print_success "OpenTelemetry Collector removed"

kubectl delete -f k8s/alertmanager.yaml --ignore-not-found=true >/dev/null 2>&1
print_success "AlertManager removed"

kubectl delete -f k8s/grafana.yaml --ignore-not-found=true >/dev/null 2>&1
print_success "Grafana removed"

kubectl delete -f k8s/prometheus.yaml --ignore-not-found=true >/dev/null 2>&1
print_success "Prometheus removed"

kubectl delete -f k8s/configmaps.yaml --ignore-not-found=true >/dev/null 2>&1
print_success "ConfigMaps removed"

echo ""

# Step 2: Delete namespace
print_step "Step 2/3: Deleting namespace..."
kubectl delete namespace intelligent-sre --ignore-not-found=true >/dev/null 2>&1

# Wait for namespace to be fully deleted
max_wait=60
elapsed=0
while kubectl get namespace intelligent-sre >/dev/null 2>&1; do
    if [ $elapsed -ge $max_wait ]; then
        print_warning "Namespace deletion is taking longer than expected. It will continue in the background."
        break
    fi
    echo -n "."
    sleep 2
    elapsed=$((elapsed + 2))
done

if ! kubectl get namespace intelligent-sre >/dev/null 2>&1; then
    print_success "Namespace deleted"
else
    print_warning "Namespace is being deleted (may take a few more seconds)"
fi

echo ""

# Step 3: Show what's left
print_step "Step 3/3: Cleanup summary..."

# Check if services are still accessible
services_still_running=false

if curl -s http://localhost:30090/api/v1/query?query=up >/dev/null 2>&1; then
    print_warning "Prometheus is still accessible (may take a moment to shut down)"
    services_still_running=true
fi

if curl -s http://localhost:30300/api/health >/dev/null 2>&1; then
    print_warning "Grafana is still accessible (may take a moment to shut down)"
    services_still_running=true
fi

if curl -s http://localhost:30080/health >/dev/null 2>&1; then
    print_warning "API is still accessible (may take a moment to shut down)"
    services_still_running=true
fi

if [ "$services_still_running" = false ]; then
    print_success "All services have been stopped"
fi

echo ""

# Display what was NOT removed
echo "╔══════════════════════════════════════════════════════╗"
echo "║              Cleanup Complete! 🧹                    ║"
echo "╚══════════════════════════════════════════════════════╝"
echo ""
echo "✓ All Kubernetes resources removed"
echo "✓ Namespace 'intelligent-sre' deleted"
echo ""
echo "📦 Still present (not removed):"
echo "   • Docker image: intelligent-sre-mcp:latest"
echo "   • Claude Desktop config: ~/Library/Application Support/Claude/claude_desktop_config.json"
echo "   • Python virtual environment: .venv/"
echo "   • Source code and manifests"
echo ""
echo "🗑️  To remove Docker image:"
echo "   docker rmi intelligent-sre-mcp:latest"
echo ""
echo "🔧 To remove Claude Desktop config:"
echo "   rm ~/Library/Application\\ Support/Claude/claude_desktop_config.json"
echo ""
echo "🐍 To remove Python virtual environment:"
echo "   rm -rf .venv"
echo ""
echo "🚀 To redeploy:"
echo "   ./setup/setup.sh"
echo ""
