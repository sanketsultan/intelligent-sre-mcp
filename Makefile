# Makefile — single entry point for all common dev operations.
# Run `make` or `make help` to see available targets.

.DEFAULT_GOAL := help

# ---------------------------------------------------------------------------
# Variables
# ---------------------------------------------------------------------------
COMPOSE     := docker compose
PYTHON      := python3
PYTEST      := pytest
RUFF        := ruff
TF          := terraform
K8S_DEV     := k8s/overlays/dev
K8S_PROD    := k8s/overlays/prod

# ---------------------------------------------------------------------------
# Help
# ---------------------------------------------------------------------------
.PHONY: help
help:
	@echo ""
	@echo "intelligent-sre-agent — development targets"
	@echo ""
	@echo "  Local (Docker Compose — no K8s required):"
	@echo "    make env          Auto-fill .env with all defaults (safe to re-run)"
	@echo "    make dev          Start full stack (API + Postgres + Prometheus + Grafana)"
	@echo "    make dev-build    Rebuild Docker image then start"
	@echo "    make dev-down     Stop and remove containers"
	@echo "    make dev-logs     Tail API container logs"
	@echo ""
	@echo "  Kubernetes (Docker Desktop / minikube):"
	@echo "    make k8s          Build image + deploy full stack to local K8s"
	@echo "    make k8s-prod     Deploy to production K8s (prod overlay)"
	@echo "    make k8s-down     Delete dev overlay resources"
	@echo "    make k8s-status   Show pod status in intelligent-sre namespace"
	@echo "    make k8s-logs     Tail API pod logs"
	@echo ""
	@echo "  Smart:"
	@echo "    make logs         Auto-detect Docker or K8s and tail the right logs"
	@echo ""
	@echo "  Quality:"
	@echo "    make test         Run unit tests"
	@echo "    make lint         Run ruff check + format (auto-fix)"
	@echo "    make tf-check     terraform fmt + tflint + checkov"
	@echo ""

# ---------------------------------------------------------------------------
# Environment
# ---------------------------------------------------------------------------
.PHONY: env
env:
	@bash scripts/setup-env.sh

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
.PHONY: _require-env
_require-env:
	@if [ ! -f .env ]; then \
	  echo ""; \
	  echo "ERR  .env not found. Run: cp .env.example .env"; \
	  echo "     Then set ANTHROPIC_API_KEY in .env and retry."; \
	  echo ""; \
	  exit 1; \
	fi

# ---------------------------------------------------------------------------
# Docker Compose (local — no K8s required)
# ---------------------------------------------------------------------------
.PHONY: dev
dev: _require-env
	$(COMPOSE) up -d
	@echo ""
	@echo "Stack is up:"
	@echo "  API:        http://localhost:8080/health"
	@echo "  Prometheus: http://localhost:9090"
	@echo "  Grafana:    http://localhost:3000  (see .env for credentials)"
	@echo ""
	@echo "Run 'make logs' to follow API logs."

.PHONY: dev-build
dev-build: _require-env
	$(COMPOSE) up -d --build

.PHONY: dev-down
dev-down:
	$(COMPOSE) down

.PHONY: dev-logs
dev-logs: _require-env
	$(COMPOSE) logs -f api

# Auto-detect running environment and tail the right logs.
.PHONY: logs
logs:
	@if kubectl get pods -n intelligent-sre >/dev/null 2>&1; then \
	  echo "==> Kubernetes detected — tailing agent logs"; \
	  kubectl logs -n intelligent-sre -l app=intelligent-sre-agent -f --tail=100; \
	elif [ -f .env ] && $(COMPOSE) ps --services --filter status=running 2>/dev/null | grep -q api; then \
	  echo "==> Docker Compose detected — tailing api logs"; \
	  $(COMPOSE) logs -f api; \
	else \
	  echo "ERR  No running environment detected."; \
	  echo "     Docker Compose: cp .env.example .env && make dev"; \
	  echo "     Kubernetes:     cp .env.example .env && ./scripts/setup.sh"; \
	fi

# ---------------------------------------------------------------------------
# Kubernetes
# ---------------------------------------------------------------------------
.PHONY: k8s
k8s:
	@bash scripts/setup.sh

.PHONY: k8s-prod
k8s-prod:
	kubectl apply -k $(K8S_PROD)

.PHONY: k8s-down
k8s-down:
	kubectl delete -k $(K8S_DEV)

.PHONY: k8s-status
k8s-status:
	kubectl get pods -n intelligent-sre

.PHONY: k8s-logs
k8s-logs:
	kubectl logs -n intelligent-sre -l app=intelligent-sre-agent -f --tail=100

# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------
.PHONY: test
test:
	$(PYTEST) tests/unit/ -v

# ---------------------------------------------------------------------------
# Lint / format
# ---------------------------------------------------------------------------
.PHONY: lint
lint:
	$(RUFF) check src/ tests/ --fix
	$(RUFF) format src/ tests/
	$(RUFF) check src/ tests/

# ---------------------------------------------------------------------------
# Terraform
# ---------------------------------------------------------------------------
.PHONY: tf-check
tf-check:
	$(TF) fmt -check -recursive terraform/
	tflint --recursive terraform/
	checkov -d terraform/ --framework terraform --compact --quiet
