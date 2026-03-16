# Intelligent SRE Agent

AI-powered SRE platform that autonomously detects, investigates, and heals production incidents using Claude.

Alertmanager fires an alert → the agent queries Prometheus, Loki, and Kubernetes → determines root cause → remediates (restart pod, patch deployment, rollback release) → posts a summary to Slack. All with a full audit trail in PostgreSQL.

## Prerequisites

- [Docker Desktop](https://www.docker.com/products/docker-desktop/) — for Docker Compose and local Kubernetes
- Python 3.10+ — for running the SRE agent CLI
- `kubectl` — for Kubernetes setup (included with Docker Desktop)
- `ANTHROPIC_API_KEY` — get one at https://console.anthropic.com

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

Fires automatically on every alert — saves to DB and runs background agent investigation.

```bash
POST http://localhost:8080/alertmanager/webhook   # receives alerts
GET  http://localhost:8080/alerts                 # list all alerts
GET  http://localhost:8080/alerts/<id>            # alert + investigation summary
```

---

## Chaos / Remediation Test

End-to-end test: deploys broken pods, triggers the automated pipeline, verifies the agent fixes them.

```bash
export ANTHROPIC_API_KEY=sk-ant-...
./scripts/test-remediation.sh
```

Failure modes simulated:

| Pod               | Failure          | Agent Fix                        |
|-------------------|------------------|----------------------------------|
| `crash-worker`    | CrashLoopBackOff | patch env var causing exit 1     |
| `dependent-worker`| Init:Error       | auto-recovers once crash-worker heals |
| `pending-worker`  | Pending          | patch impossible nodeSelector    |
| `sick-api`        | Running/NotReady | patch broken readiness probe     |

---

## Stack

- **App**: FastAPI + PostgreSQL
- **Observability**: Prometheus + Grafana + Loki + Jaeger + OpenTelemetry + Alertmanager
- **Infra**: Terraform (AWS EKS + RDS) + Kubernetes (Kustomize overlays)
- **Security**: OPA/Gatekeeper, Falco, Pod Security Standards
- **CI**: GitHub Actions — ruff, pytest, docker build, kubeconform, tflint, checkov

---

## Troubleshooting

```bash
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
