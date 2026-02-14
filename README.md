# Intelligent SRE MCP

> **Talk to your Kubernetes cluster through Claude Desktop.**  
> Ask questions in plain English and get real-time insights from Prometheus, Grafana, and K8s.

An intelligent SRE copilot that connects Claude Desktop to your entire monitoring stack via the Model Context Protocol (MCP).

## What It Does

- 🔍 **Detects anomalies** - CPU spikes, memory leaks, crash loops
- 📊 **Analyzes patterns** - Recurring failures, resource exhaustion, cascading issues
- 🔗 **Correlates signals** - Links metrics, events, and alerts for root cause analysis
- 💯 **Calculates health scores** - 0-100 system health with recommendations
- 🤖 **Natural language queries** - "Is my system healthy?", "Why is this pod failing?"

**Example queries:**
- "Detect anomalies in my cluster"
- "What patterns do you see in pod failures?"
- "Show me correlations between restarts and events"
- "Run comprehensive analysis"

## Quick Start

**One command to set up everything:**

```bash
git clone https://github.com/sanketsultan/intelligent-sre-mcp.git
cd intelligent-sre-mcp
./setup.sh
```

This will:
- ✓ Build and deploy to Kubernetes
- ✓ Start Prometheus, Grafana, and monitoring stack
- ✓ Configure Claude Desktop integration
- ✓ Verify all services are running

**Then restart Claude Desktop:**
```bash
killall Claude && open -a Claude
```

**Test it:**
```
Ask Claude: "Show me all pods in the intelligent-sre namespace"
```

---

## 17 MCP Tools for Claude

Claude has access to these tools to query your infrastructure:

**Prometheus (3):** `prom_query`, `prom_query_range`, `prom_targets`  
**Kubernetes (8):** `k8s_get_all_pods`, `k8s_get_failing_pods`, `k8s_get_pod_logs`, `k8s_describe_pod`, `k8s_get_nodes`, `k8s_get_deployment`, `k8s_get_events`, `k8s_watch_events`  
**Detection (6):** `detect_anomalies`, `get_health_score`, `detect_patterns`, `detect_correlations`, `comprehensive_analysis`, `detect_metric_spike`

---

## Services

Access these directly or through Claude:

- **Prometheus**: http://localhost:30090
- **Grafana**: http://localhost:30300 (admin/admin)
- **API**: http://localhost:30080
- **AlertManager**: http://localhost:30093
- **Jaeger**: http://localhost:30686

---

## Testing

**Quick test everything:**
```bash
./run_tests.sh
```

**Recommended - End-to-End Test:**
```bash
./tests/test-e2e-with-claude.sh
```
Deploys test infrastructure, detects issues, lets you test with Claude, auto-cleans up. Perfect for demos!

**See [tests/README.md](tests/README.md) for more options.**

---

## Troubleshooting

**API not responding:**
```bash
kubectl get pods -n intelligent-sre
curl http://localhost:30080/health
```

**Claude can't connect:**
```bash
killall Claude && open -a Claude
cat ~/Library/Application\ Support/Claude/claude_desktop_config.json
```

**Check logs:**
```bash
kubectl logs -n intelligent-sre deployment/intelligent-sre-mcp --tail=50
```

---

## Cleanup

```bash
./cleanup.sh
```

---

## What's Inside

- **Monitoring Stack**: Prometheus, Grafana, AlertManager, Jaeger, OpenTelemetry
- **Metrics Collection**: kube-state-metrics, Node Exporter, demo metrics
- **Python API**: FastAPI server with 17 MCP tools
- **Detection Engines**: Anomaly detection, pattern recognition, correlation analysis
- **Test Suite**: Automated tests, interactive scenarios, E2E testing

**See full documentation in project files.**

---

## License

This project is licensed under the **MIT License**.
