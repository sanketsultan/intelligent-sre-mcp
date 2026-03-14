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
- `k8s/kustomization.yaml` — single entry point for all K8s resources
- `terraform/environments/aws/main.tf` — top-level AWS environment

## Dev commands
```bash
docker compose up          # run full stack locally
pytest tests/unit/              # run tests
ruff check src/            # lint
ruff format src/           # format
terraform fmt -recursive terraform/
tflint --chdir terraform/modules/eks
checkov -d terraform/ --framework terraform --compact --quiet
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
