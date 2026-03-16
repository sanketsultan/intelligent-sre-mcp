# Intelligent SRE Agent

AI-powered SRE platform that autonomously detects, investigates, and heals production incidents using Claude.

Alertmanager fires an alert, the agent queries Prometheus, Loki, and Kubernetes, determines root cause, remediates (restart pod, patch deployment, rollback release), and posts a summary to Slack. All with a full audit trail in PostgreSQL.

## Prerequisites

- [Docker Desktop](https://www.docker.com/products/docker-desktop/) for Docker Compose and local Kubernetes
- Python 3.10+ for running the SRE agent CLI
- `kubectl` for Kubernetes setup (included with Docker Desktop)
- `ANTHROPIC_API_KEY` from https://console.anthropic.com

---

## Quick Start

### Docker Compose (recommended for local dev)

```bash
git clone https://github.com/sanketsultan/intelligent-sre-agent.git
cd intelligent-sre-agent
cp .env.example .env        # then set ANTHROPIC_API_KEY in .env
make dev
```

| Service    | URL                   |
|------------|-----------------------|
| API        | http://localhost:8080 |
| Prometheus | http://localhost:9090 |
| Grafana    | http://localhost:3000 |

### Kubernetes (Docker Desktop)

```bash
cp .env.example .env        # then set ANTHROPIC_API_KEY in .env
./scripts/setup.sh
```

| Service      | URL                    |
|--------------|------------------------|
| API          | http://localhost:30080 |
| Prometheus   | http://localhost:30090 |
| Grafana      | http://localhost:30300 |
| Alertmanager | http://localhost:30093 |
| Jaeger       | http://localhost:30686 |

Set `ANTHROPIC_API_KEY` in `.env` to enable the agent and Slack bot.

---

## How It Works

When an alert fires:

1. Phase 1 - haiku investigates (always runs, cheap and fast)
2. Phase 2 - sonnet remediates if severity meets the threshold (default: critical)
3. Phase 3 - if sonnet leaves anything broken, opus escalates with alternative approaches
4. If opus also fails, posts an urgent Slack message for human intervention

Every 5 minutes a CronJob hits `/health/proactive-check`. If the health score drops below the threshold (default 50/100), investigation and remediation run automatically without waiting for an alert.

---

## SRE Agent

```bash
# Investigate
python -m intelligent_sre_agent.sre_agent "What is the current health of the system?"

# Investigate + remediate
python -m intelligent_sre_agent.sre_agent --remediate "Pods are CrashLoopBackOff in production"

# Model selection (default: haiku for speed/cost)
python -m intelligent_sre_agent.sre_agent --model sonnet "High 5xx error rate on checkout"
python -m intelligent_sre_agent.sre_agent --model opus  "Database down, 100% error rate"
```

---

## Slack Bot

```bash
./scripts/run-slack-bot.sh
# Requires SLACK_BOT_TOKEN + SLACK_APP_TOKEN + ANTHROPIC_API_KEY in .env
```

| Command                   | Action                  |
|---------------------------|-------------------------|
| `/sre <prompt>`           | Investigate (read-only) |
| `/sre remediate <prompt>` | Investigate and heal    |
| `/sre runbooks`           | List runbooks           |
| `@SRE-Bot <prompt>`       | Mention shortcut        |

---

## Alertmanager Webhook

Fires automatically on every alert. Saves to DB and runs background agent investigation.

```bash
POST http://localhost:8080/alertmanager/webhook   # receives alerts
GET  http://localhost:8080/alerts                 # list all alerts
GET  http://localhost:8080/alerts/<id>            # alert + investigation summary
```

---

## Tuning the Agent

Set these env vars in `k8s/base/app/intelligent-sre-agent.yaml` or `.env`:

| Var | Default | What it does |
|-----|---------|--------------|
| `SRE_AUTO_REMEDIATE_SEVERITY` | `critical` | Set to `warning` to also auto-heal warning alerts |
| `SRE_PROACTIVE_HEALTH_THRESHOLD` | `50` | Health score below which proactive check triggers remediation |
| `SRE_REMEDIATION_MODEL` | `claude-sonnet-4-5` | Model for Phase 2 remediation |
| `SRE_ESCALATION_MODEL` | `claude-opus-4-6` | Model used if sonnet leaves things broken |
| `SRE_MODEL` | `claude-haiku-4-5` | Model for Phase 1 investigation |
| `SRE_MAX_TOKENS` | `4096` | Output token ceiling |

---

## Chaos / Remediation Test

End-to-end test: deploys broken pods, triggers the automated pipeline, verifies the agent fixes them.

```bash
export ANTHROPIC_API_KEY=sk-ant-...
./scripts/test-remediation.sh
```

Failure modes simulated:

| Pod               | Failure          | Agent Fix                             |
|-------------------|------------------|---------------------------------------|
| `crash-worker`    | CrashLoopBackOff | patch env var causing exit 1          |
| `dependent-worker`| Init:Error       | auto-recovers once crash-worker heals |
| `pending-worker`  | Pending          | patch impossible nodeSelector         |
| `sick-api`        | Running/NotReady | patch broken readiness probe          |

---

## Stack

- **App**: FastAPI + PostgreSQL
- **Observability**: Prometheus + Grafana + Loki + Jaeger + OpenTelemetry + Alertmanager
- **Infra**: Terraform (AWS EKS + RDS) + Kubernetes (Kustomize overlays)
- **Security**: OPA/Gatekeeper, Falco, Pod Security Standards
- **CI**: GitHub Actions with ruff, pytest, docker build, kubeconform, tflint, checkov

---

## Troubleshooting

```bash
# Auto-detect environment and tail logs
make logs

# Docker Compose
make dev-logs
docker compose ps

# Kubernetes
kubectl get pods -n intelligent-sre
kubectl logs -n intelligent-sre deployment/intelligent-sre-agent --tail=50
```

---

## License

MIT
