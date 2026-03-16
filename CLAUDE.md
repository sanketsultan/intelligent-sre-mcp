# intelligent-sre-agent

AI-powered SRE platform exposing MCP tools for autonomous incident detection, triage, and healing.

## Stack
- **App**: Python (FastAPI) in `src/intelligent_sre_agent/`
- **Infra**: Terraform (`terraform/modules/eks`, `terraform/modules/rds`, `terraform/environments/aws`)
- **K8s**: Kustomize manifests in `k8s/` (Prometheus, Grafana, Loki, Gatekeeper, Falco, SLO/DORA rules)
- **CI**: `.github/workflows/ci.yml` - ruff, pytest, docker build, kubeconform, tflint, checkov

## Key files
- `src/intelligent_sre_agent/api_server.py` - FastAPI app, structured JSON logging, Alertmanager webhook + alert history
- `src/intelligent_sre_agent/server.py` - MCP stdio server entry point
- `src/intelligent_sre_agent/sre_agent.py` - Claude-powered SRE incident response agent
- `src/intelligent_sre_agent/alert_store.py` - Alert persistence (alerts table, investigation + remediation summaries)
- `src/intelligent_sre_agent/runbooks.py` - structured runbooks (DB pool, latency, error rates)
- `src/intelligent_sre_agent/bot/slack_bot.py` - Slack bot (Socket Mode, /sre slash command, @mention)
- `k8s/kustomization.yaml` - single entry point for all K8s resources
- `terraform/environments/aws/main.tf` - top-level AWS environment

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
# Model selection - controls cost vs capability (default: haiku):
#   haiku   claude-haiku-4-5   ~$0.001/run   routine health checks        (default)
#   sonnet  claude-sonnet-4-5  ~$0.05/run    complex incidents
#   opus    claude-opus-4-6    ~$0.10/run    critical production incidents
#
# Set once via env var to avoid typing --model every time:
#   export SRE_MODEL=sonnet
#
python -m intelligent_sre_agent.sre_agent "What is the current health of the system?"
python -m intelligent_sre_agent.sre_agent --model sonnet "High 5xx error rate on checkout service"
python -m intelligent_sre_agent.sre_agent --model sonnet --remediate "Pods are CrashLoopBackOff in production"
python -m intelligent_sre_agent.sre_agent --model opus "Database down, 100% error rate"
# Or use the convenience script:
./scripts/run-sre-agent.sh "High 5xx error rate on checkout service"

# Run the Slack bot (requires SLACK_BOT_TOKEN + SLACK_APP_TOKEN + ANTHROPIC_API_KEY)
python -m intelligent_sre_agent.bot.slack_bot
# Or use the convenience script:
./scripts/run-slack-bot.sh

# Slack bot commands:
#   /sre <prompt>                - investigate only (read-only)
#   /sre remediate <prompt>      - investigate + heal
#   /sre runbooks                - list structured runbooks
#   /sre help                    - show help
#   @SRE-Bot <prompt>            - mention shortcut for investigate
#   @SRE-Bot --remediate <prompt>- mention shortcut for remediate

# Alertmanager webhook (fires on every alert; saves to DB + runs agent investigation):
#   POST http://localhost:30080/alertmanager/webhook
#   GET  http://localhost:30080/alerts           - list all saved alerts
#   GET  http://localhost:30080/alerts/<id>      - single alert with investigation

# Webhook-triggered agent model selection (set in k8s/base/app/intelligent-sre-agent.yaml):
#   SRE_MODEL                       - Phase 1 investigation model (default: claude-haiku-4-5)
#   SRE_REMEDIATION_MODEL           - Phase 2 remediation model (default: claude-sonnet-4-5)
#   SRE_ESCALATION_MODEL            - Phase 3 escalation model (default: claude-opus-4-6)
#   SRE_AUTO_REMEDIATE_SEVERITY     - minimum severity for auto-remediation (default: critical)
#   SRE_PROACTIVE_HEALTH_THRESHOLD  - health score below which proactive check remediates (default: 50)
#
# Three-phase healing pipeline:
#   Phase 1 - haiku investigates (always runs)
#   Phase 2 - sonnet remediates if severity >= SRE_AUTO_REMEDIATE_SEVERITY
#   Phase 3 - if "STILL BROKEN" in Phase 2 output, opus tries alternative approaches
#   If Phase 3 also fails, posts an urgent Slack message for human intervention
#
# Proactive CronJob (k8s/base/app/proactive-check-cronjob.yaml):
#   Runs every 5 minutes, POSTs to /health/proactive-check
#   If health score < SRE_PROACTIVE_HEALTH_THRESHOLD, triggers remediation without waiting for an alert
#
# The in-pod agent uses API_URL=http://localhost:8080 (internal port, set in K8s manifest).
# Do NOT use localhost:30080 for in-pod agent calls - that is the NodePort (external only).
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

Failure modes simulated (`k8s/chaos/`) - all fixable via `patch_deployment`:

| Pod | Failure | Root cause | Agent fix |
|---|---|---|---|
| `crash-worker` | CrashLoopBackOff | `SIMULATE_CRASH=true` env var causes exit 1 | patch env var to `false` |
| `dependent-worker` | Init:Error | init blocked by crash-worker being down (cascade) | auto-recovers once crash-worker is healthy |
| `pending-worker` | Pending | impossible `nodeSelector: hardware-accelerator: a100-gpu` | patch `nodeSelector` to `null` |
| `sick-api` | Running/NotReady | readiness probe targets port 9999 (not listening) | patch `readinessProbe` to `null` |

Healing tool priority: `patch_deployment` (fix config) > `rollback_deployment` (revert bad deploy) > `restart_pod` (transient) > `scale_deployment` to 0 (emergency stop only).

New endpoint: `POST /healing/patch-deployment` - applies a K8s strategic merge patch to fix a deployment in place without stopping it.

## Token cost tuning

Every agent run logs actual token usage + estimated cost.
CLI output: `[tokens] input=1243  output=312  cost~=$0.00504  model=claude-sonnet-4-5`
K8s log (JSON): `{"msg":"SRE agent finished","input_tokens":1243,"output_tokens":312,"estimated_cost_usd":0.005043}`

### Pricing reference (per million tokens)
| Model | Input | Output | Typical cost/run |
|---|---|---|---|
| `claude-haiku-4-5` | $0.25 | $1.25 | ~$0.001 - routine checks (default Phase 1) |
| `claude-sonnet-4-5` | $3.00 | $15.00 | ~$0.005–$0.05 - remediation (default Phase 2) |
| `claude-opus-4-6` | $15.00 | $75.00 | ~$0.10 - critical incidents only |

### Cost levers (env vars in `k8s/base/app/intelligent-sre-agent.yaml`)
| Var | Default | Effect |
|---|---|---|
| `SRE_MODEL` | `claude-haiku-4-5` | Phase 1 investigation model - cheapest, fast |
| `SRE_REMEDIATION_MODEL` | `claude-sonnet-4-5` | Phase 2 remediation model - more capable |
| `SRE_MAX_TOKENS` | `4096` | Output token ceiling - you pay for tokens generated, not this limit |
| `SRE_INVESTIGATION_CTX_CHARS` | `3000` | Max chars of Phase 1 text embedded in Phase 2 prompt - cuts sonnet input tokens |

### Quick tuning
```bash
# Cheapest possible (investigation only, no remediation):
kubectl set env deploy/intelligent-sre-agent -n intelligent-sre SRE_MODEL=haiku

# More aggressive context truncation (smaller Phase 2 input):
kubectl set env deploy/intelligent-sre-agent -n intelligent-sre SRE_INVESTIGATION_CTX_CHARS=1500

# Raise output ceiling if remediation_summary looks cut off:
kubectl set env deploy/intelligent-sre-agent -n intelligent-sre SRE_MAX_TOKENS=6144

# CLI: see real token cost per run
python -m intelligent_sre_agent.sre_agent "check health"
# prints: [tokens] input=842  output=201  cost~=$0.00028  model=claude-haiku-4-5
```

## Slash commands

Dev quality (`.claude/commands/dev/`):
- `/dev:lint` - ruff check + format, auto-fix all issues
- `/dev:test` - run pytest, fix failures
- `/dev:tf-check` - terraform fmt + tflint + checkov, fix all issues
- `/dev:ci-fix` - inspect latest CI run, fix all failing jobs
- `/dev:pr` - create PR to master with summary and test plan

SRE / ops (`.claude/commands/skills/`):
- `/skills:sre <prompt>` - run SRE agent against live stack; add `--remediate` to heal
- `/skills:deploy` - docker build + kubectl apply + rollout status
- `/skills:k8s-status` - cluster health summary with service endpoint checks
- `/skills:chaos deploy|teardown|status` - inject or clean up chaos pods
- `/skills:chaos-test` - full end-to-end remediation test
- `/skills:postmortem <incident>` - generate structured postmortem report for a resolved incident

Also available (`.claude/commands/dev/`):
- `/dev:update-docs` - scan recent commits and update README.md + CLAUDE.md accordingly

## Conventions
- Python: ruff enforced, no new deps without pyproject.toml update
- Terraform: AWS provider `~> 5.0`, checkov:skip annotations go **inside** resource/data blocks
- K8s: base/ + overlays/dev (local) + overlays/prod; entry: kubectl apply -k k8s/overlays/dev
- Commits: conventional commits (`feat:`, `fix:`, `chore:`)
- Branch: `claude/sharp-davinci` → PR to `master`
- No emojis anywhere - not in code, comments, docstrings, commit messages, PR descriptions, or bot responses
