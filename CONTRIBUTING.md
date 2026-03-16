# Contributing to intelligent-sre-agent

Thank you for contributing! This guide covers the local dev setup, code style, testing, and the PR process.

## Quick start

```bash
# 1. Clone
git clone https://github.com/sanketsultan/intelligent-sre-agent.git
cd intelligent-sre-agent

# 2. Python environment (3.10+)
python -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate

# 3. Install all dependencies
pip install -r requirements.txt
pip install -e .
pip install pytest pytest-cov pytest-asyncio ruff pre-commit

# 4. Install pre-commit hooks
pre-commit install

# 5. Copy environment file
cp .env.example .env
# Edit .env – at minimum set POSTGRES_PASSWORD and GRAFANA_ADMIN_PASSWORD
```

## Running locally (Docker Compose)

```bash
# Start the full stack (API + Postgres + Prometheus + Grafana + OTel)
docker compose up -d

# Dev mode: live reload + SQLite (no Postgres needed)
docker compose -f docker-compose.yml -f docker-compose.override.yml up

# Verify
curl http://localhost:8080/health
```

## Running locally (Kubernetes / minikube)

```bash
# Start minikube
minikube start

# Build and load image
docker build -t intelligent-sre-agent:latest .
minikube image load intelligent-sre-agent:latest

# Deploy
kubectl apply -k k8s/

# Wait for readiness
kubectl -n intelligent-sre rollout status deployment/intelligent-sre-agent

# Access API
kubectl -n intelligent-sre port-forward svc/intelligent-sre-agent 8080:8080
curl http://localhost:8080/health
```

## Code style

This project uses **ruff** for linting and formatting.

```bash
# Check linting
ruff check src/ tests/

# Auto-fix linting issues
ruff check --fix src/ tests/

# Format
ruff format src/ tests/
```

Configuration is in `pyproject.toml` under `[tool.ruff]`. Line length is 100.

Pre-commit hooks run `ruff` automatically on every commit.

## Testing

```bash
# Run all unit tests
pytest

# Run with coverage report
pytest --cov=src/intelligent_sre_mcp --cov-report=term-missing

# Run a specific test file
pytest tests/test_detection.py -v

# Run E2E tests (requires running K8s cluster + deployed stack)
./tests/test-e2e-with-claude.sh
```

Tests live in `tests/`. Unit tests in `test_*.py` files run without a live cluster.
Shell-based E2E tests (`*.sh`) require a running K8s deployment.

## Pull request process

1. **Fork** the repo and create a branch: `git checkout -b feat/my-feature`
2. Make your changes and add tests where appropriate
3. Ensure `pre-commit run --all-files` passes
4. Ensure `pytest` passes
5. Open a PR against `master`

CI will automatically run lint, tests, K8s manifest validation, and a Docker build.
PRs must pass all CI checks before merging.

## Commit message convention

```
<type>: <short description>

[optional body]
```

Types: `feat`, `fix`, `chore`, `docs`, `refactor`, `test`, `ci`

Example: `feat: add recurring issue detection endpoint`

## Releasing

Releases are driven by git tags:

```bash
git tag v1.0.0
git push origin v1.0.0
```

This triggers the `release.yml` workflow which builds a multi-arch Docker image
and pushes it to `ghcr.io/sanketsultan/intelligent-sre-agent:v1.0.0`.

## Project structure

```
intelligent-sre-agent/
├── src/intelligent_sre_mcp/   Python package
│   ├── api_server.py           FastAPI application (29 endpoints)
│   ├── api_client.py           MCP client implementation
│   ├── server.py               MCP stdio server entry point
│   ├── config.py               Settings loader
│   └── tools/                  Detection + healing engines
├── k8s/                        Kubernetes manifests (kustomize)
├── tests/                      Unit tests + E2E shell scripts
├── setup/                      Setup scripts + config files
├── .github/workflows/          CI/CD pipelines
├── docker-compose.yml          Full-stack Docker Compose
└── Dockerfile                  Multi-stage production image
```
