# Intelligent SRE MCP

A Kubernetes-native SRE monitoring platform that combines observability, metrics, and AI to provide intelligent infrastructure insights through Claude Desktop.

> An intelligent SRE copilot that lets you ask questions about your infrastructure in plain English and get answers directly from Prometheus, Grafana, and other monitoring tools using Claude Desktop via the Model Context Protocol (MCP).

**Think of it as:**
> "Claude, but connected to your entire monitoring stack running in Kubernetes."

---

## What This Project Does

This project provides a complete monitoring platform deployed on Kubernetes that:
- **Collects metrics** via Prometheus, Node Exporter, and OpenTelemetry Collector
- **Visualizes data** through Grafana dashboards
- **Exposes monitoring data** to Claude Desktop via a FastAPI-based MCP server
- **Enables natural language queries** like:
  - "Is my system healthy?"
  - "Which targets are down?"
  - "What's the CPU usage right now?"
  - "Show me memory usage trends"

Claude doesn't guess—it queries real metrics from your Kubernetes cluster.

---

## Architecture

```text
Claude Desktop
  |
  | (MCP over HTTP)
  v
intelligent-sre-mcp API (FastAPI in K8s)
  |
  | (PromQL queries)
  v
Prometheus (Kubernetes)
  |
  +-- scrapes --> Node Exporter (system metrics)
  +-- scrapes --> OpenTelemetry Collector (traces/metrics)
  +-- scrapes --> Demo Metrics (sample data)
  |
  v
Grafana (Kubernetes) <-- Visualizes metrics
```

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

### 5. Restart Claude Desktop

```bash
# Quit Claude completely
killall Claude

# Reopen Claude Desktop
open -a Claude
```

#### 5. Restart Claude Desktop

```bash
# Quit Claude completely
killall Claude

# Reopen Claude Desktop
open -a Claude
```

#### 6. Test in Claude CPU usage?"
- "Show me memory availability"
- "How many targets are down?"
- "Query prometheus_build_info"

**Intelligent Questions:**
- "Is my system healthy?"
- "Are there any performance issues?"
- "Which services should I be concerned about?"

---

## Components

### Monitoring Stack (Kubernetes)
- **Prometheus** - Metrics collection and storage
- **Grafana** - Visualization and dashboards
- **AlertManager** - Alert routing and notifications
- **Node Exporter** - System metrics collection
- **OpenTelemetry Collector** - Traces and metrics pipeline
- **Jaeger** - Distributed tracing UI

### Python Application
- **FastAPI Server** (`api_server.py`) - HTTP API for Kubernetes deployment
- **MCP Client** (`api_client.py`) - Claude Desktop integration wrapper
- **OpenTelemetry Instrumentation** - Automatic tracing for API calls

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
│   ├── alertmanager.yaml         # AlertManager deployment
│   ├── otel-collector.yaml       # OpenTelemetry Collector
│   ├── node-exporter.yaml        # Node Exporter DaemonSet
│   ├── jaeger.yaml               # Jaeger tracing
│   └── demo-metrics.yaml         # Sample metrics generator
├── src/intelligent_sre_mcp/      # Python application
│   ├── server.py                 # Original MCP stdio server
│   ├── api_server.py             # FastAPI HTTP server (K8s)
│   ├── api_client.py             # MCP client for Claude
│   └── tools/                    # Query tools
├── Dockerfile                    # Container image for API
├── setup.sh                      # One-command setup script
├── cleanup.sh                    # One-command cleanup script
├── setup_claude.sh               # Claude Desktop configuration
└── run_mcp_api.sh               # Wrapper for Claude integration
```

---

## Documentation

- **[Kubernetes Deployment Guide](KUBERNETES_DEPLOYMENT.md)** - Complete K8s setup instructions
- **[Claude Setup Guide](CLAUDE_SETUP.md)** - Detailed Claude Desktop integration
- **[Grafana Setup Guide](GRAFANA_SETUP.md)** - Dashboard configuration and imports

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
- Prometheus: http://localhost:30090
- Grafana: http://localhost:30300 (admin/admin)
- API: http://localhost:30080
- Jaeger: http://localhost:30686

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
