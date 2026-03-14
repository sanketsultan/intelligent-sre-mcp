# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added
- GitHub Actions CI pipeline: lint (ruff), test (pytest), K8s manifest validation (kubeconform), Docker build + Trivy scan
- GitHub Actions release pipeline: multi-arch Docker build/push to GHCR on `v*` tags
- `docker-compose.yml` for full-stack non-Kubernetes deployment
- `docker-compose.override.yml` for local development with live reload
- `k8s/network-policy.yaml` – namespace-level network isolation
- `k8s/resource-limits.yaml` – ResourceQuota + LimitRange for the namespace
- `k8s/hpa.yaml` – HorizontalPodAutoscaler (min 1, max 3 replicas)
- `setup/prometheus.yml` – standalone Prometheus config for Docker Compose
- `setup/otel-collector.yaml` – standalone OTel config for Docker Compose
- `.pre-commit-config.yaml` – ruff, ruff-format, hadolint, and file hygiene hooks
- `.env.example` – documents every environment variable with inline comments
- `CHANGELOG.md` and `CONTRIBUTING.md`

### Changed
- `requirements.txt` – all 12 dependencies now have version ranges (`>=min,<major+1`)
- `pyproject.toml` – added `[tool.ruff]`, `[tool.pytest.ini_options]`, `[tool.coverage]`
- `Dockerfile` – pinned to `python:3.10.17-slim-bookworm`, non-root user (uid 1000), multi-stage build, real `HEALTHCHECK` against `/health`
- `k8s/intelligent-sre-mcp.yaml` – replaced dummy `exec: sys.exit(0)` probes with real `httpGet /health` liveness/readiness/startup probes; added pod + container `SecurityContext` (non-root, read-only FS, drop ALL capabilities)
- `k8s/prometheus.yaml` – replaced `emptyDir` with a 10 Gi PVC; pinned image to `prom/prometheus:v2.55.1`; added `--storage.tsdb.retention.time=15d`; added health probes and SecurityContext
- `k8s/kustomization.yaml` – added new manifests (`resource-limits`, `network-policy`, `hpa`)

## [0.1.0] - 2025-01-01

### Added
- Initial release: FastAPI MCP API server with 29 endpoints
- Kubernetes tools (pod/node/deployment/event diagnostics)
- Anomaly detection engine (Z-score, CPU/memory thresholds)
- Pattern recognition engine (recurring failures, cyclic spikes)
- Correlation engine (metric-to-event, event-to-metric)
- Self-healing actions with HealingActionLimiter safety guards
- Audit logging and problem tracking (SQLite + PostgreSQL)
- Agent activity tracking and learning endpoints
- Complete Kubernetes manifests with Prometheus, Grafana, AlertManager, Jaeger
- 25+ Prometheus alert rules
- MCP stdio server for Claude Desktop integration
- Comprehensive test suite (unit tests + shell-based E2E)
