# Intelligent SRE MCP

A Kubernetes-native SRE monitoring platform that combines observability, metrics, and AI to provide intelligent infrastructure insights through Claude Desktop.

> An intelligent SRE copilot that lets you ask questions about your infrastructure in plain English and get answers directly from Prometheus, Grafana, and other monitoring tools using Claude Desktop via the Model Context Protocol (MCP).

**Think of it as:**
> "Claude, but connected to your entire monitoring stack running in Kubernetes."

---

## What This Project Does

This project provides a complete monitoring and self-healing platform deployed on Kubernetes that:
- **Collects metrics** via Prometheus, Node Exporter, kube-state-metrics, and OpenTelemetry Collector
- **Visualizes data** through Grafana dashboards
- **Exposes monitoring data** to Claude Desktop via a FastAPI-based MCP server
- **Provides Kubernetes diagnostics** - Pod status, logs, events, node health
- **Enables natural language queries** like:
  - "Is my system healthy?"
  - "Which pods are failing?"
  - "Show me logs from the crashed container"
  - "What's the CPU usage right now?"
  - "Describe the grafana pod in detail"

Claude doesn't guess—it queries real metrics and live Kubernetes state from your cluster.

---

## Architecture

```text
Claude Desktop (11 MCP Tools)
  |
  | MCP over HTTP (stdio wrapper)
  v
intelligent-sre-mcp API (FastAPI in K8s)
  |
  +-- Prometheus API --> PromQL queries for metrics
  |
  +-- Kubernetes API --> Pod/Node/Deployment diagnostics
       |
       v
Prometheus (Kubernetes) <-- Grafana visualizes
  |
  +-- scrapes --> kube-state-metrics (K8s object metrics)
  +-- scrapes --> Node Exporter (system metrics)
  +-- scrapes --> OpenTelemetry Collector (traces/metrics)
  +-- scrapes --> Demo Metrics (sample data)
```

---

## Features

### 11 MCP Tools Available to Claude

**Prometheus Metrics (3 tools):**
1. `prom_query` - Execute PromQL queries (e.g., `up`, `cpu_usage`, custom metrics)
2. `prom_query_range` - Time-series range queries for trending analysis
3. `prom_targets` - List all Prometheus scrape targets and their health status

**Kubernetes Diagnostics (8 tools):**
4. `k8s_get_all_pods` - List all pods across namespaces with status, restarts, age
5. `k8s_get_failing_pods` - Identify pods with errors, CrashLoopBackOff, restarts
6. `k8s_get_pod_logs` - Retrieve container logs from any pod (supports tail lines)
7. `k8s_describe_pod` - Detailed pod information (events, containers, volumes, status)
8. `k8s_get_nodes` - Node health, CPU/memory capacity and allocation
9. `k8s_get_deployment` - Deployment replica status and rollout state
10. `k8s_get_events` - Recent Kubernetes events filtered by namespace or resource
11. `k8s_watch_events` - (Future) Real-time event streaming

---

## Prerequisites

- **Kubernetes cluster** (Docker Desktop, Minikube, or any K8s cluster)
- **kubectl** configured and connected to your cluster
- **Docker** for building the Python API container
- **Python 3.10+** for local development
- **Claude Desktop** app

---

## Quick Start

### One-Command Setup

```bash
git clone https://github.com/sanketsultan/intelligent-sre-mcp.git
cd intelligent-sre-mcp
./setup.sh
```

This single script will:
- ✓ Build the Docker image
- ✓ Deploy all services to Kubernetes
- ✓ Wait for pods to be ready
- ✓ Verify all endpoints
- ✓ Set up Python environment
- ✓ Configure Claude Desktop

### Manual Setup

If you prefer step-by-step deployment:

#### 1. Clone the repository

```bash
git clone https://github.com/sanketsultan/intelligent-sre-mcp.git
cd intelligent-sre-mcp
```

#### 2. Deploy to Kubernetes

```bash
# Build Docker image
docker build -t intelligent-sre-mcp:latest .

# Deploy the entire monitoring stack
kubectl apply -f k8s/

# Verify all pods are running
kubectl get pods -n intelligent-sre

# Check services
kubectl get svc -n intelligent-sre
```

**Services exposed:**
- **Prometheus**: http://localhost:30090
- **Grafana**: http://localhost:30300 (admin/admin)
- **Intelligent SRE API**: http://localhost:30080
- **AlertManager**: http://localhost:30093
- **Jaeger**: http://localhost:30686

#### 3. Verify the deployment

```bash
# Test Prometheus query
curl "http://localhost:30090/api/v1/query?query=up"

# Test API health
curl http://localhost:30080/health

# Check Grafana health
curl http://localhost:30300/api/health
```

#### 4. Configure Claude Desktop

Edit `~/Library/Application Support/Claude/claude_desktop_config.json`:

```json
{
  "mcpServers": {
    "intelligent-sre-mcp": {
      "command": "/Users/YOUR_USERNAME/Desktop/intelligent-sre-mcp/run_mcp_api.sh",
      "args": [],
      "env": {
        "API_URL": "http://localhost:30080"
      }
    }
  }
}
```

#### 5. Restart Claude Desktop

```bash
# Quit Claude completely
killall Claude

# Reopen Claude Desktop
open -a Claude
```

#### 6. Test in Claude

Open Claude Desktop and try these prompts:

**Prometheus Metrics:**
- "Run prom_query with query 'up'"
- "What's the current CPU usage?"
- "Show me memory availability"
- "How many targets are down?"

**Kubernetes Diagnostics:**
- "Show me all pods in the intelligent-sre namespace"
- "Are there any failing pods?"
- "Get logs from the prometheus pod in intelligent-sre namespace"
- "Describe the grafana pod in detail"
- "What's the status of all nodes?"
- "Show me recent Kubernetes events"

**Intelligent Questions:**
- "Is my system healthy?"
- "Are there any performance issues?"
- "Which services should I be concerned about?"

---

## Components

### Monitoring Stack (Kubernetes)
- **Prometheus** - Metrics collection and storage (scraping 5 targets)
- **Grafana** - Visualization and dashboards
- **kube-state-metrics** - Kubernetes object state metrics (pods, deployments, nodes)
- **Node Exporter** - System metrics collection
- **OpenTelemetry Collector** - Traces and metrics pipeline
- **Jaeger** - Distributed tracing UI
- **AlertManager** - Alert routing and notifications

### Python Application
- **FastAPI Server** (`api_server.py`) - HTTP API with 7 Kubernetes diagnostic endpoints
- **MCP Client** (`api_client.py`) - Claude Desktop integration wrapper (11 MCP tools)
- **Kubernetes Tools** (`tools/k8s_tools.py`) - Pod, node, deployment, event diagnostics
- **Prometheus Tools** (`tools/metrics.py`) - PromQL query execution

---

## Project Structure

```
intelligent-sre-mcp/
├── k8s/                          # Kubernetes manifests
│   ├── namespace.yaml            # intelligent-sre namespace
│   ├── configmaps.yaml           # Prometheus, AlertManager, OTEL configs
│   ├── prometheus.yaml           # Prometheus deployment
│   ├── grafana.yaml              # Grafana with datasources
│   ├── intelligent-sre-mcp.yaml  # FastAPI application
│   ├── rbac.yaml                 # ServiceAccount + RBAC for K8s API access
│   ├── kube-state-metrics.yaml   # K8s object state metrics
│   ├── alertmanager.yaml         # AlertManager deployment
│   ├── otel-collector.yaml       # OpenTelemetry Collector
│   ├── node-exporter.yaml        # Node Exporter DaemonSet
│   ├── jaeger.yaml               # Jaeger tracing
│   └── demo-metrics.yaml         # Sample metrics generator
├── src/intelligent_sre_mcp/      # Python application
│   ├── server.py                 # Original MCP stdio server
│   ├── api_server.py             # FastAPI HTTP server (7 K8s endpoints)
│   ├── api_client.py             # MCP client for Claude (11 tools)
│   └── tools/
│       ├── metrics.py            # Prometheus query tools
│       └── k8s_tools.py          # Kubernetes diagnostic tools (NEW)
├── Dockerfile                    # Container image for API
├── setup.sh                      # One-command setup script
├── cleanup.sh                    # One-command cleanup script
├── setup_claude.sh               # Claude Desktop configuration
└── run_mcp_api.sh               # Wrapper for Claude integration
```

---

## Development

### Local Development
```bash
# Set up Python environment
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

# Run the API server locally
python src/intelligent_sre_mcp/api_server.py
```

### Building Docker Image
```bash
docker build -t intelligent-sre-mcp:latest .
```

### Accessing Services
- **Prometheus**: http://localhost:30090 (metrics database, PromQL queries)
- **Grafana**: http://localhost:30300 (dashboards, login: admin/admin)
- **API**: http://localhost:30080 (FastAPI endpoints, health check at `/health`)
- **Jaeger**: http://localhost:30686 (distributed tracing UI)
- **kube-state-metrics**: http://localhost:30081 (K8s object metrics)

### Verifying Deployment

```bash
# Check all pods are running
kubectl get pods -n intelligent-sre

# Check Prometheus targets (should show 5 healthy targets)
curl http://localhost:30090/api/v1/targets | jq '.data.activeTargets[] | {job: .labels.job, health: .health}'

# Test API health
curl http://localhost:30080/health

# Test Claude integration (requires Claude Desktop configured)
# In Claude Desktop, ask: "Show me all pods in the intelligent-sre namespace"
```

---

## Troubleshooting

### Pod Won't Start
```bash
# Check pod status
kubectl get pods -n intelligent-sre

# View pod logs
kubectl logs -n intelligent-sre <pod-name>

# Describe pod for events
kubectl describe pod -n intelligent-sre <pod-name>
```

### Claude Can't Connect to API
1. Verify API is running: `kubectl get pods -n intelligent-sre | grep intelligent-sre-mcp`
2. Check NodePort service: `kubectl get svc -n intelligent-sre intelligent-sre-mcp-service`
3. Test API locally: `curl http://localhost:30080/health`
4. Restart Claude Desktop: `killall Claude && open -a Claude`
5. Check Claude config path: `~/Library/Application Support/Claude/claude_desktop_config.json`

### Prometheus Not Scraping
```bash
# Check Prometheus targets
curl http://localhost:30090/api/v1/targets

# View Prometheus logs
kubectl logs -n intelligent-sre deployment/prometheus

# Verify ConfigMap
kubectl get configmap -n intelligent-sre prometheus-config -o yaml
```

### Permission Errors (403 Forbidden)
```bash
# Verify RBAC is deployed
kubectl get clusterrole intelligent-sre-mcp-role
kubectl get clusterrolebinding intelligent-sre-mcp-binding

# Check ServiceAccount
kubectl get serviceaccount -n intelligent-sre intelligent-sre-mcp
```

---

## Cleanup

```bash
# Remove all Kubernetes resources
./cleanup.sh

# Or manually
kubectl delete namespace intelligent-sre
```

---

## License

This project is licensed under the **MIT License**.
