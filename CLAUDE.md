# intelligent-sre-mcp

AI-powered SRE platform exposing MCP tools for autonomous incident detection, triage, and healing.

## Stack
- **App**: Python (FastAPI) in `src/intelligent_sre_mcp/`
- **Infra**: Terraform (`terraform/modules/eks`, `terraform/modules/rds`, `terraform/environments/aws`)
- **K8s**: Kustomize manifests in `k8s/` (Prometheus, Grafana, Loki, Gatekeeper, Falco, SLO/DORA rules)
- **CI**: `.github/workflows/ci.yml` — ruff, pytest, docker build, kubeconform, tflint, checkov

## Key files
- `src/intelligent_sre_mcp/api_server.py` — FastAPI app, structured JSON logging
- `src/intelligent_sre_mcp/server.py` — MCP stdio server entry point
- `src/intelligent_sre_mcp/sre_agent.py` — Claude-powered SRE incident response agent
- `src/intelligent_sre_mcp/runbooks.py` — structured runbooks (DB pool, latency, error rates)
- `src/intelligent_sre_mcp/bot/discord_bot.py` — Discord bot interface for the SRE agent
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
python -m intelligent_sre_mcp.sre_agent "What is the current health of the system?"
python -m intelligent_sre_mcp.sre_agent --remediate "Pods are CrashLoopBackOff in production"
# Or use the convenience script:
./scripts/run-sre-agent.sh "High 5xx error rate on checkout service"

# Run the Discord bot (requires DISCORD_BOT_TOKEN + ANTHROPIC_API_KEY)
python -m intelligent_sre_mcp.bot.discord_bot
# Or use the convenience script:
./scripts/run-discord-bot.sh

# Discord bot commands (in any channel):
#   !sre <prompt>                — investigate only (read-only)
#   !sre remediate <prompt>      — investigate + heal
#   !sre runbooks                — list structured runbooks
#   @SRE-Bot <prompt>            — mention shortcut for investigate
#   @SRE-Bot --remediate <prompt>— mention shortcut for remediate
```

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
