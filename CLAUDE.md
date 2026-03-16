# intelligent-sre-mcp

AI-powered SRE platform exposing MCP tools for autonomous incident detection, triage, and healing.

## Stack
- **App**: Python (FastAPI) in `src/intelligent_sre_mcp/`
- **Infra**: Terraform (`terraform/modules/eks`, `terraform/modules/rds`, `terraform/environments/aws`)
- **K8s**: Kustomize manifests in `k8s/` (Prometheus, Grafana, Loki, Gatekeeper, Falco, SLO/DORA rules)
- **CI**: `.github/workflows/ci.yml` — ruff, pytest, docker build, kubeconform, tflint, checkov

## Key files
- `src/intelligent_sre_mcp/api_server.py` — FastAPI app, structured JSON logging, Alertmanager webhook + alert history
- `src/intelligent_sre_mcp/server.py` — MCP stdio server entry point
- `src/intelligent_sre_mcp/sre_agent.py` — Claude-powered SRE incident response agent
- `src/intelligent_sre_mcp/alert_store.py` — Alert persistence (alerts table, investigation + remediation summaries)
- `src/intelligent_sre_mcp/runbooks.py` — structured runbooks (DB pool, latency, error rates)
- `src/intelligent_sre_mcp/bot/slack_bot.py` — Slack bot (Socket Mode, /sre slash command, @mention)
- `k8s/kustomization.yaml` — single entry point for all K8s resources
- `terraform/environments/aws/main.tf` — top-level AWS environment

## Dev commands
```bash
docker compose up          # run full stack locally
pytest tests/unit/         # run tests
ruff check src/            # lint
ruff format src/           # format
terraform fmt -recursive terraform/
tflint --chdir terraform/modules/eks
checkov -d terraform/ --framework terraform --compact --quiet

# Run the SRE agent (requires ANTHROPIC_API_KEY and API_URL pointing to a running stack)
#
# Model selection — controls cost vs capability (default: haiku):
#   haiku   claude-haiku-4-5   ~$0.001/run   routine health checks        (default)
#   sonnet  claude-sonnet-4-5  ~$0.05/run    complex incidents
#   opus    claude-opus-4-6    ~$0.10/run    critical production incidents
#
# Set once via env var to avoid typing --model every time:
#   export SRE_MODEL=sonnet
#
python -m intelligent_sre_mcp.sre_agent "What is the current health of the system?"
python -m intelligent_sre_mcp.sre_agent --model sonnet "High 5xx error rate on checkout service"
python -m intelligent_sre_mcp.sre_agent --model sonnet --remediate "Pods are CrashLoopBackOff in production"
python -m intelligent_sre_mcp.sre_agent --model opus "Database down, 100% error rate"
# Or use the convenience script:
./scripts/run-sre-agent.sh "High 5xx error rate on checkout service"

# Run the Slack bot (requires SLACK_BOT_TOKEN + SLACK_APP_TOKEN + ANTHROPIC_API_KEY)
python -m intelligent_sre_mcp.bot.slack_bot
# Or use the convenience script:
./scripts/run-slack-bot.sh

# Slack bot commands:
#   /sre <prompt>                — investigate only (read-only)
#   /sre remediate <prompt>      — investigate + heal
#   /sre runbooks                — list structured runbooks
#   /sre help                    — show help
#   @SRE-Bot <prompt>            — mention shortcut for investigate
#   @SRE-Bot --remediate <prompt>— mention shortcut for remediate

# Alertmanager webhook (fires on every alert; saves to DB + runs agent investigation):
#   POST http://localhost:30080/alertmanager/webhook
#   GET  http://localhost:30080/alerts           — list all saved alerts
#   GET  http://localhost:30080/alerts/<id>      — single alert with investigation

# Webhook-triggered agent model selection (set in k8s/base/app/intelligent-sre-mcp.yaml):
#   SRE_MODEL               — Phase 1 investigation model (default: claude-haiku-4-5, cheap/fast)
#   SRE_REMEDIATION_MODEL   — Phase 2 remediation model (default: claude-sonnet-4-5, more capable)
#
# Why two models: haiku is sufficient for read-only investigation but too weak to reliably
# execute multi-step tool-based remediation (scale_deployment, delete_failed_pods chains).
# Sonnet is the minimum recommended capability for the healing pass.
#
# The in-pod agent uses API_URL=http://localhost:8080 (internal port, set in K8s manifest).
# Do NOT use localhost:30080 for in-pod agent calls — that is the NodePort (external only).
```

## Chaos / remediation test

End-to-end test that deploys broken pods, triggers the automated pipeline, and verifies the agent remediates them:

```bash
export ANTHROPIC_API_KEY=sk-ant-...
./scripts/test-remediation.sh

# Keep chaos pods after test for manual inspection:
SKIP_CLEANUP=1 ./scripts/test-remediation.sh

# Deploy / teardown chaos pods manually:
kubectl apply  -k k8s/chaos/
kubectl delete -k k8s/chaos/
```

Failure modes simulated (`k8s/chaos/`):

| Pod | Failure | Root cause |
|---|---|---|
| `crash-worker` | CrashLoopBackOff | container exits with code 1 |
| `dependent-worker` | Init:Error | init container blocked by crash-worker being down (cascade) |
| `pending-worker` | Pending | requests 100 CPU cores — impossible to schedule |
| `sick-api` | Running/NotReady | readiness probe always fails (port not open) |

Agent healing actions used: `delete_failed_pods`, `scale_deployment` (to 0).

## Slash commands
- `/lint` — ruff check + format, auto-fix all issues
- `/test` — run pytest, fix failures
- `/tf-check` — terraform fmt + tflint + checkov, fix all issues
- `/ci-fix` — inspect latest CI run, fix all failing jobs
- `/pr` — create PR to master with summary and test plan

## Conventions
- Python: ruff enforced, no new deps without pyproject.toml update
- Terraform: AWS provider `~> 5.0`, checkov:skip annotations go **inside** resource/data blocks
- K8s: base/ + overlays/dev (local) + overlays/prod; entry: kubectl apply -k k8s/overlays/dev
- Commits: conventional commits (`feat:`, `fix:`, `chore:`)
- Branch: `claude/sharp-davinci` → PR to `master`
- No emojis anywhere — not in code, comments, docstrings, commit messages, PR descriptions, or bot responses
