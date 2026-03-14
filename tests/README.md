# Tests

## Structure

```
tests/
├── unit/          # pytest unit tests (run in CI)
│   ├── test_detection.py
│   └── test_healing_actions.py
└── e2e/           # end-to-end shell scripts (require live stack)
    ├── run-all-tests.sh
    ├── test-scenarios.sh
    ├── test-healing-scenarios.sh
    ├── test-e2e-full-automation.sh
    ├── test-e2e-with-claude.sh
    └── test-phase5.sh
```

## Running tests

**Unit tests (no dependencies):**
```bash
pytest tests/unit/
```

**Unit tests with coverage:**
```bash
pytest tests/unit/ --cov=src --cov-report=term-missing
```

**E2E tests (requires live stack on :30080):**
```bash
# Start the stack first
docker compose up -d
# or: kubectl apply -k k8s/overlays/dev

# Run all e2e scenarios
bash tests/e2e/run-all-tests.sh
```

## CI behaviour

- Unit tests run on every push/PR across Python 3.10/3.11/3.12
- E2E tests are excluded from CI (require live API server)
- Integration tests (marked `@pytest.mark.integration`) are skipped in CI via `-m "not integration"`
