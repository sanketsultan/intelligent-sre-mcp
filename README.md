# Intelligent SRE MCP

> **Talk to your Kubernetes cluster through Claude Desktop.**  
> Ask questions in plain English and get real-time insights from Prometheus, Grafana, and K8s.  
> **NEW:** Claude can now **automatically heal** issues with built-in safety controls!  
> **NEW:** Every action is **auto-correlated** and **audit-logged** to the database.

An intelligent SRE copilot that connects Claude Desktop to your entire monitoring stack via the Model Context Protocol (MCP).

## What It Does

- 🔍 **Detects anomalies** - CPU spikes, memory leaks, crash loops
- 📊 **Analyzes patterns** - Recurring failures, resource exhaustion, cascading issues
- 🔗 **Correlates signals** - Links metrics, events, and alerts for root cause analysis
- 💯 **Calculates health scores** - 0-100 system health with recommendations
- 🔧 **Self-healing actions** - Restart pods, scale deployments, rollback releases (NEW!)
- 🤖 **Natural language queries** - "Is my system healthy?", "Fix that crashing pod"

**Example queries:**
- "Detect anomalies in my cluster"
- "What patterns do you see in pod failures?"
- "Restart the api-server pod that keeps crashing"
- "Scale up the frontend deployment to 5 replicas"
- "Show me the healing action history"

## Quick Start

**Setup scripts now live in `setup/`:**

```bash
ls setup/
```

**One command for everything (K8s + Claude):**

```bash
git clone https://github.com/sanketsultan/intelligent-sre-mcp.git
cd intelligent-sre-mcp
./setup/quickstart.sh all
```

This will:
- ✓ Build and deploy to Kubernetes
- ✓ Start Prometheus, Grafana, and monitoring stack
- ✓ Configure Claude Desktop integration
- ✓ Verify all services are running

**Only want Claude setup?**
```bash
./setup/quickstart.sh claude
```

**Only want Kubernetes setup?**
```bash
./setup/quickstart.sh k8s
```

**Docker-only (API container):**
```bash
./setup/quickstart.sh docker
```

**Test it:**
```
Ask Claude: "Show me all pods in the intelligent-sre namespace"
```

## Docker Image

Pull the public image:

```bash
docker pull sanketsultan/intelligent-sre-mcp:latest
```

Optional run (exposes API on port 30080):

```bash
docker run --rm -p 30080:8080 sanketsultan/intelligent-sre-mcp:latest
```

---

## MCP Tools for Claude

Claude has access to these tools to query and manage your infrastructure:

**Prometheus (3):** `prom_query`, `prom_query_range`, `prom_targets`  
**Kubernetes (8):** `k8s_get_all_pods`, `k8s_get_failing_pods`, `k8s_get_pod_logs`, `k8s_describe_pod`, `k8s_get_nodes`, `k8s_get_deployment`, `k8s_get_events`, `k8s_watch_events`  
**Detection (6):** `detect_anomalies`, `get_health_score`, `detect_patterns`, `detect_correlations`, `comprehensive_analysis`, `detect_metric_spike`  
**Healing (9):** `restart_pod`, `delete_failed_pods`, `evict_pod_from_node`, `drain_node`, `scale_deployment`, `rollback_deployment`, `cordon_node`, `uncordon_node`, `get_healing_history`
**Learning (9):** `get_action_stats`, `get_recurring_issues`, `record_action_outcome`, `record_agent_activity`, `get_agent_activity`, `create_problem`, `update_problem`, `list_problems`, `list_tool_invocations` 🆕

---

## Phase 5: Learning & Optimization

Track healing effectiveness, recurring issues, and outcomes.

**Example prompts:**
- "Show healing action stats for the last 24 hours"
- "List recurring issues in the last 24 hours"
- "Record outcome for action ID 42 as success with 60s recovery"

**Persist action history (optional):**
```bash
export ACTION_HISTORY_DB=/path/to/intelligent_sre_actions.db
```

**Use Postgres for action history (recommended in K8s):**
```bash
export ACTION_HISTORY_DB=postgresql://sre:srepassword@postgres:5432/sre
```

## Correlation & Audit Logging (Auto)

We now **auto-correlate** every request, tool invocation, and healing action to a single **problem** record for auditability and model improvement.

**What gets captured**
- **`problems`**: Canonical problem records with `fingerprint`, status, and timestamps.
- **`tool_invocations`**: Every API/tool call with method, path, query/body, status, duration, and `problem_id`.
- **`agent_activity`**: High-signal agent intent + inputs + action + outcome with `problem_id`.
- **`healing_actions`**: All remediation actions with `problem_id`.

**How correlation works**
- Each request creates or reuses a **problem** based on a stable `fingerprint`.
- `problem_id` is propagated via request context and attached to all logs automatically.
- You can override correlation per request with header **`X-Problem-Id`**.

**Why this matters (staff-engineer view)**
- **Auditability**: One thread of evidence per incident for compliance and RCA.
- **Model improvement**: High-quality traces enable training signal without noise.
- **Operational visibility**: See tool usage, success/failure, and outcomes by incident.

**Operational guidance**
- **Retention**: Add a scheduled job to purge old rows (e.g., 30–90 days).
- **PII/Secrets**: Keep payload capture minimal; redact sensitive fields upstream.
- **Performance**: These writes are lightweight; keep Postgres tuned and indexed.

**Quick checks**
```bash
kubectl exec -n intelligent-sre postgres-0 -- psql -U sre -d sre -c \
"SELECT id, title, fingerprint, status FROM problems ORDER BY id DESC LIMIT 20;"
```
```bash
kubectl exec -n intelligent-sre postgres-0 -- psql -U sre -d sre -c \
"SELECT id, method, path, status_code, problem_id FROM tool_invocations ORDER BY id DESC LIMIT 20;"
```

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
