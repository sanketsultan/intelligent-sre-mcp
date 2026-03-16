# Intelligent SRE MCP

AI-powered SRE platform exposing MCP tools for autonomous incident detection, triage, and healing.

Talk to your Kubernetes cluster through Claude Desktop. Ask questions in plain English and get
real-time insights from Prometheus, Grafana, and K8s. The platform detects issues, matches
pre-approved playbooks, auto-remediates when confidence exceeds 80%, and defers to humans
otherwise — with a full audit trail in PostgreSQL.

## What It Does

- Detects anomalies — CPU spikes, memory leaks, crash loops
- Analyzes patterns — recurring failures, resource exhaustion, cascading issues
- Correlates signals — links metrics, events, and alerts for root cause analysis
- Calculates health scores — 0-100 system health with recommendations
- Auto-remediates — restart pods, scale deployments, rollback releases, with confidence scoring
- Natural language queries — "Is my system healthy?", "Run remediation in production namespace"

---

## Quick Start

### Option A: Docker Compose (no Kubernetes required — recommended for local dev)

```bash
git clone https://github.com/sanketsultan/intelligent-sre-agent.git
cd intelligent-sre-agent
make dev
```

`make dev` copies `.env.example` to `.env` (first run only) then starts:

| Service     | URL                        |
|-------------|----------------------------|
| API         | http://localhost:8080      |
| Prometheus  | http://localhost:9090      |
| Grafana     | http://localhost:3000      |
| OTel        | http://localhost:4317 gRPC |

Set `ANTHROPIC_API_KEY` in `.env` to enable the SRE agent and Slack bot.

```bash
make dev-logs     # tail API logs
make dev-down     # stop everything
make dev-build    # rebuild image + start
```

### Option B: Kubernetes

```bash
make k8s          # deploy dev overlay  (kubectl apply -k k8s/overlays/dev)
make k8s-prod     # deploy prod overlay (kubectl apply -k k8s/overlays/prod)
make k8s-status   # show pod status
make k8s-down     # delete dev resources
```

Or use the script directly:

```bash
./scripts/quickstart.sh dev    # Docker Compose (default)
./scripts/quickstart.sh k8s    # Kubernetes
./scripts/quickstart.sh local  # Python venv only
```

---

## All Make Targets

```
make help        # list all targets
make env         # copy .env.example to .env (first-time only)
make dev         # docker compose up -d
make dev-build   # rebuild image + start
make dev-down    # docker compose down
make dev-logs    # tail API container logs
make k8s         # kubectl apply -k k8s/overlays/dev
make k8s-prod    # kubectl apply -k k8s/overlays/prod
make k8s-down    # kubectl delete -k k8s/overlays/dev
make k8s-status  # kubectl get pods -n intelligent-sre
make test        # pytest tests/unit/
make lint        # ruff check + format (auto-fix)
make tf-check    # terraform fmt + tflint + checkov
```

---

## SRE Agent

Requires `ANTHROPIC_API_KEY` in `.env` and a running API stack.

```bash
# Investigate
python -m intelligent_sre_mcp.sre_agent "What is the current health of the system?"

# Investigate + auto-remediate
python -m intelligent_sre_mcp.sre_agent --remediate "Pods are CrashLoopBackOff in production"

# Convenience script
./scripts/run-sre-agent.sh "High 5xx error rate on checkout service"
```

---

## Auto-Remediation API

| Endpoint                  | Method | Description                           |
|---------------------------|--------|---------------------------------------|
| `/remediation/run`        | POST   | Detect issues and run playbooks       |
| `/remediation/history`    | GET    | Audit log of all remediation runs     |
| `/remediation/playbooks`  | GET    | List all pre-approved playbooks       |

```bash
# Dry run — see what would happen without executing
curl -s -X POST http://localhost:8080/remediation/run \
  -H "Content-Type: application/json" \
  -d '{"namespace": "production", "dry_run": true}' | jq .

# View recent runs
curl -s http://localhost:8080/remediation/history | jq .
```

Pre-approved playbooks: `crashloop_restart`, `oom_killed_scale`, `image_pull_rollback`,
`pod_failed_cleanup`, `high_restart_restart`. Issues with confidence below 0.80 are deferred
to a human via the configured Slack notify callback.

---

## Slack Bot

```bash
# Requires SLACK_BOT_TOKEN + SLACK_APP_TOKEN + ANTHROPIC_API_KEY in .env
python -m intelligent_sre_mcp.bot.slack_bot
# Or:
./scripts/run-slack-bot.sh
```

Slack commands:

| Command                   | Action                    |
|---------------------------|---------------------------|
| `/sre <prompt>`           | Investigate (read-only)   |
| `/sre remediate <prompt>` | Investigate and heal      |
| `/sre runbooks`           | List structured runbooks  |
| `/sre help`               | Show help                 |
| `@SRE-Bot <prompt>`       | Mention shortcut          |

---

## Alertmanager Webhook

```bash
# Fires on every alert — saves to DB and runs background agent investigation
POST http://localhost:8080/alertmanager/webhook

# List all saved alerts
GET  http://localhost:8080/alerts

# Single alert with investigation summary
GET  http://localhost:8080/alerts/<id>
```

---

## MCP Tools

**Prometheus (3):** `prom_query`, `prom_query_range`, `prom_targets`

**Kubernetes (8):** `k8s_get_all_pods`, `k8s_get_failing_pods`, `k8s_get_pod_logs`,
`k8s_describe_pod`, `k8s_get_nodes`, `k8s_get_deployment`, `k8s_get_events`, `k8s_watch_events`

**Detection (6):** `detect_anomalies`, `get_health_score`, `detect_patterns`,
`detect_correlations`, `comprehensive_analysis`, `detect_metric_spike`

**Healing (9):** `restart_pod`, `delete_failed_pods`, `evict_pod_from_node`, `drain_node`,
`scale_deployment`, `rollback_deployment`, `cordon_node`, `uncordon_node`, `get_healing_history`

**Learning (9):** `get_action_stats`, `get_recurring_issues`, `record_action_outcome`,
`record_agent_activity`, `get_agent_activity`, `create_problem`, `update_problem`,
`list_problems`, `list_tool_invocations`

---

## Services (Kubernetes NodePort)

| Service      | URL                       | Credentials         |
|--------------|---------------------------|---------------------|
| API          | http://localhost:30080    |                     |
| Prometheus   | http://localhost:30090    |                     |
| Grafana      | http://localhost:30300    | see .env            |
| Alertmanager | http://localhost:30093    |                     |
| Jaeger       | http://localhost:30686    |                     |

---

## Testing

```bash
make test               # run unit tests
pytest tests/unit/ -v   # verbose
```

---

## Troubleshooting

**API not responding (Docker Compose):**
```bash
make dev-logs
docker compose ps
```

**API not responding (K8s):**
```bash
kubectl get pods -n intelligent-sre
kubectl logs -n intelligent-sre deployment/intelligent-sre-agent --tail=50
```

**Remediation defers everything to human:**
Check that `ANTHROPIC_API_KEY` and Slack tokens are set. Confidence below 0.80 always defers.
Critical namespaces (`kube-system`, `cert-manager`, etc.) always defer regardless of confidence.

---

## What Is Inside

- **Stack**: FastAPI + PostgreSQL + Prometheus + Grafana + OpenTelemetry + Alertmanager
- **Infra**: Terraform modules for AWS EKS + RDS; Kubernetes manifests with Kustomize overlays
- **Security**: OPA/Gatekeeper admission policies, Falco runtime rules, Pod Security Standards
- **Observability**: SLO/error budget recording rules, DORA metric rules, Grafana dashboards
- **CI**: GitHub Actions — ruff, pytest, docker build, kubeconform, tflint, checkov

---

## License

MIT
