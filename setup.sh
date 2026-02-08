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

# Function to wait for pods to be ready
wait_for_pods() {
    local namespace=$1
    local max_wait=300  # 5 minutes
    local elapsed=0
    
    print_step "Waiting for all pods to be ready..."
    
    while [ $elapsed -lt $max_wait ]; do
        local not_ready=$(kubectl get pods -n "$namespace" --no-headers 2>/dev/null | grep -v "Running\|Completed" | wc -l | tr -d ' ')
        
        if [ "$not_ready" -eq 0 ]; then
            print_success "All pods are ready!"
            return 0
        fi
        
        echo -n "."
        sleep 5
        elapsed=$((elapsed + 5))
    done
    
    print_error "Timeout waiting for pods to be ready"
    kubectl get pods -n "$namespace"
    return 1
}

# Banner
echo ""
echo "╔══════════════════════════════════════════════════════╗"
echo "║     Intelligent SRE MCP - Complete Setup Script     ║"
echo "╚══════════════════════════════════════════════════════╝"
echo ""

# Check prerequisites
print_step "Checking prerequisites..."

if ! command_exists kubectl; then
    print_error "kubectl is not installed. Please install kubectl first."
    exit 1
fi
print_success "kubectl is installed"

if ! command_exists docker; then
    print_error "docker is not installed. Please install Docker first."
    exit 1
fi
print_success "docker is installed"

if ! command_exists python3; then
    print_error "python3 is not installed. Please install Python 3.10+ first."
    exit 1
fi
print_success "python3 is installed"

# Check kubectl connectivity
if ! kubectl cluster-info >/dev/null 2>&1; then
    print_error "Cannot connect to Kubernetes cluster. Please ensure your cluster is running and kubectl is configured."
    exit 1
fi
print_success "Kubernetes cluster is accessible"

# Get the project directory
PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$PROJECT_DIR"

print_success "Project directory: $PROJECT_DIR"
echo ""

# Step 1: Build Docker image
print_step "Step 1/5: Building Docker image..."
if docker build -t intelligent-sre-mcp:latest . >/dev/null 2>&1; then
    print_success "Docker image built successfully"
else
    print_error "Failed to build Docker image"
    exit 1
fi
echo ""

# Step 2: Deploy to Kubernetes
print_step "Step 2/5: Deploying to Kubernetes..."

# Create namespace
kubectl apply -f k8s/namespace.yaml >/dev/null 2>&1
print_success "Namespace created"

# Apply all manifests
kubectl apply -f k8s/configmaps.yaml >/dev/null 2>&1
print_success "ConfigMaps created"

kubectl apply -f k8s/prometheus.yaml >/dev/null 2>&1
print_success "Prometheus deployed"

kubectl apply -f k8s/grafana.yaml >/dev/null 2>&1
print_success "Grafana deployed"

kubectl apply -f k8s/alertmanager.yaml >/dev/null 2>&1
print_success "AlertManager deployed"

kubectl apply -f k8s/otel-collector.yaml >/dev/null 2>&1
print_success "OpenTelemetry Collector deployed"

kubectl apply -f k8s/node-exporter.yaml >/dev/null 2>&1
print_success "Node Exporter deployed"

kubectl apply -f k8s/jaeger.yaml >/dev/null 2>&1
print_success "Jaeger deployed"

kubectl apply -f k8s/demo-metrics.yaml >/dev/null 2>&1
print_success "Demo Metrics deployed"

kubectl apply -f k8s/intelligent-sre-mcp.yaml >/dev/null 2>&1
print_success "Intelligent SRE MCP API deployed"

echo ""

# Wait for pods to be ready
wait_for_pods "intelligent-sre"
echo ""

# Step 3: Verify deployment
print_step "Step 3/5: Verifying deployment..."

# Check Prometheus
if curl -s http://localhost:30090/api/v1/query?query=up >/dev/null 2>&1; then
    print_success "Prometheus is accessible at http://localhost:30090"
else
    print_warning "Prometheus may not be ready yet at http://localhost:30090"
fi

# Check Grafana
if curl -s http://localhost:30300/api/health >/dev/null 2>&1; then
    print_success "Grafana is accessible at http://localhost:30300 (admin/admin)"
else
    print_warning "Grafana may not be ready yet at http://localhost:30300"
fi

# Check API
if curl -s http://localhost:30080/health >/dev/null 2>&1; then
    print_success "Intelligent SRE API is accessible at http://localhost:30080"
else
    print_warning "API may not be ready yet at http://localhost:30080"
fi

# Check AlertManager
if curl -s http://localhost:30093/-/healthy >/dev/null 2>&1; then
    print_success "AlertManager is accessible at http://localhost:30093"
else
    print_warning "AlertManager may not be ready yet at http://localhost:30093"
fi

# Check Jaeger
if curl -s http://localhost:30686 >/dev/null 2>&1; then
    print_success "Jaeger is accessible at http://localhost:30686"
else
    print_warning "Jaeger may not be ready yet at http://localhost:30686"
fi

echo ""

# Step 4: Set up Python environment (optional)
print_step "Step 4/5: Setting up Python environment (optional)..."
if [ ! -d ".venv" ]; then
    python3 -m venv .venv
    source .venv/bin/activate
    pip install -q --upgrade pip setuptools wheel
    pip install -q -r requirements.txt
    print_success "Python virtual environment created"
else
    print_success "Python virtual environment already exists"
fi
echo ""

# Step 5: Configure Claude Desktop
print_step "Step 5/5: Configuring Claude Desktop..."

CLAUDE_CONFIG_DIR="$HOME/Library/Application Support/Claude"
CLAUDE_CONFIG_FILE="$CLAUDE_CONFIG_DIR/claude_desktop_config.json"

# Create Claude config directory if it doesn't exist
mkdir -p "$CLAUDE_CONFIG_DIR"

# Create or update Claude config
cat > "$CLAUDE_CONFIG_FILE" << EOF
{
  "mcpServers": {
    "intelligent-sre-mcp": {
      "command": "$PROJECT_DIR/run_mcp_api.sh",
      "args": [],
      "env": {
        "API_URL": "http://localhost:30080"
      }
    }
  }
}
EOF

print_success "Claude Desktop configured at: $CLAUDE_CONFIG_FILE"
echo ""

# Display summary
echo ""
echo "╔══════════════════════════════════════════════════════╗"
echo "║              Setup Complete! 🎉                      ║"
echo "╚══════════════════════════════════════════════════════╝"
echo ""
echo "📊 Access your services:"
echo "   • Prometheus:    http://localhost:30090"
echo "   • Grafana:       http://localhost:30300  (admin/admin)"
echo "   • API:           http://localhost:30080"
echo "   • AlertManager:  http://localhost:30093"
echo "   • Jaeger:        http://localhost:30686"
echo ""
echo "🤖 Claude Desktop:"
echo "   1. Quit Claude Desktop completely (Cmd+Q or killall Claude)"
echo "   2. Reopen Claude Desktop"
echo "   3. Try prompts like:"
echo "      • 'Run health_check to verify the monitoring system'"
echo "      • 'What's the current CPU usage?'"
echo "      • 'Is my system healthy?'"
echo ""
echo "📚 Documentation:"
echo "   • KUBERNETES_DEPLOYMENT.md - Deployment details"
echo "   • CLAUDE_SETUP.md          - Claude integration guide"
echo "   • GRAFANA_SETUP.md         - Dashboard setup"
echo ""
echo "🧹 To remove everything:"
echo "   ./cleanup.sh"
echo ""
