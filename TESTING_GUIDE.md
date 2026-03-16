# Intelligent SRE MCP - Testing Guide

## 🧪 Comprehensive Test Suite

This guide covers all testing approaches for the Intelligent SRE MCP, designed to match the application's architecture.

## Table of Contents

- [Quick Start](#quick-start)
- [Test Architecture](#test-architecture)
- [Test Runners](#test-runners)
- [Test Categories](#test-categories)
- [Usage Examples](#usage-examples)
- [CI/CD Integration](#cicd-integration)

---

## Quick Start

### Run All Tests (Recommended)

```bash
# Run complete test suite
./tests/run-all-tests.sh

# Run with verbose output
./tests/run-all-tests.sh -v

# Stop on first failure
./tests/run-all-tests.sh -f

# Dry run (see what would be tested)
./tests/run-all-tests.sh -d
```

### Run Specific Test Categories

```bash
# Phase 1: Observability
./tests/test-scenarios.sh   # Choose options 1-4

# Phase 2: Detection
./tests/test-scenarios.sh   # Choose options 5-11

# Phase 3: Healing Actions
./tests/test-healing-scenarios.sh

# Automated Python tests
python3 tests/test_healing_actions.py
```

---

## Test Architecture

The test suite is organized to mirror the application's 3-phase architecture:

```
┌─────────────────────────────────────────────────────────────┐
│                     Test Orchestrator                        │
│                  (run-all-tests.sh)                         │
└─────────────────────────────────────────────────────────────┘
                            ↓
┌─────────────────────────────────────────────────────────────┐
│  Phase 0: Infrastructure                                     │
│  • Kubernetes cluster connectivity                          │
│  • Namespace and deployment health                          │
│  • API server availability                                  │
│  • Prometheus health (if deployed)                          │
└─────────────────────────────────────────────────────────────┘
                            ↓
┌─────────────────────────────────────────────────────────────┐
│  Phase 1: Observability                                      │
│  • get_metrics (CPU, Memory, Network)                       │
│  • get_logs (Real-time log retrieval)                       │
│  • get_traces (Distributed tracing)                         │
└─────────────────────────────────────────────────────────────┘
                            ↓
┌─────────────────────────────────────────────────────────────┐
│  Phase 2: Detection                                          │
│  • detect_anomalies (CPU, Memory, Network)                  │
│  • detect_patterns (Error spikes, Restart loops)            │
│  • get_health_score (Namespace, Pod-level)                  │
│  • analyze_correlations (Multi-metric)                      │
│  • perform_rca (Root cause analysis)                        │
└─────────────────────────────────────────────────────────────┘
                            ↓
┌─────────────────────────────────────────────────────────────┐
│  Phase 3: Self-Healing                                       │
│  • restart_pod (Dry-run & Actual)                           │
│  • delete_failed_pods (With blast radius control)           │
│  • scale_deployment (Dynamic scaling)                       │
│  • rollback_deployment (Version control)                    │
│  • cordon_node / uncordon_node (Node management)           │
│  • get_healing_history (Audit trail)                        │
└─────────────────────────────────────────────────────────────┘
                            ↓
┌─────────────────────────────────────────────────────────────┐
│  Phase 4: Integration                                        │
│  • End-to-end workflows                                     │
│  • Detection → Healing pipelines                            │
│  • Cross-phase interactions                                 │
└─────────────────────────────────────────────────────────────┘
                            ↓
┌─────────────────────────────────────────────────────────────┐
│  Phase 5: Safety Validation                                  │
│  • Rate limiting (10 actions/hour)                          │
│  • Blast radius control (5 pods max)                        │
│  • Dry-run mode verification                                │
│  • Cooldown period enforcement                              │
└─────────────────────────────────────────────────────────────┘
```

---

## Test Runners

### 1. Comprehensive Test Orchestrator (`run-all-tests.sh`)

**Purpose**: Smart test runner that executes all tests in the correct architectural order.

**Features**:
- ✅ Automatic dependency detection
- ✅ Architecture-based test flow
- ✅ Colored output with progress tracking
- ✅ Detailed test summaries
- ✅ Fail-fast and verbose modes
- ✅ Dry-run capability

**Usage**:
```bash
# Basic run
./tests/run-all-tests.sh

# Verbose mode (see all test output)
./tests/run-all-tests.sh -v

# Fail-fast (stop on first error)
./tests/run-all-tests.sh -f

# Dry run (preview tests without executing)
./tests/run-all-tests.sh -d

# Help
./tests/run-all-tests.sh -h
```

**Output Example**:
```
╔═══════════════════════════════════════════════════════════════════╗
║        🧪 INTELLIGENT SRE MCP - COMPREHENSIVE TEST SUITE 🧪      ║
╚═══════════════════════════════════════════════════════════════════╝

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
▶ Phase 0: Infrastructure Health
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

ℹ Running: Kubernetes cluster connectivity
✓ Kubernetes cluster connectivity
ℹ Running: intelligent-sre namespace exists
✓ intelligent-sre namespace exists
...

Test Execution Summary
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Total Tests:    45
Passed:         45
Failed:         0
Skipped:        0

╔═══════════════════════════════════════════════════════════════════╗
║                   ✓ ALL TESTS PASSED! 🎉                         ║
╚═══════════════════════════════════════════════════════════════════╝
```

---

### 2. Interactive Test Scenarios (`test-scenarios.sh`)

**Purpose**: Menu-driven interactive testing for Phases 1 & 2.

**Features**:
- ✅ User-friendly menu interface
- ✅ Real-time test execution
- ✅ Scenario-based testing
- ✅ Color-coded output

**Usage**:
```bash
./tests/test-scenarios.sh
# Select option from menu (1-12)
```

**Test Options**:
1. Metrics Test - CPU usage
2. Metrics Test - Memory usage
3. Metrics Test - Network usage
4. Logs Test - Recent logs
5. Anomaly Detection - CPU
6. Anomaly Detection - Memory
7. Pattern Detection - Error spikes
8. Pattern Detection - Restart loops
9. Health Score - Namespace level
10. Correlation Analysis
11. Root Cause Analysis
12. Self-Healing Actions Test

---

### 3. Healing Actions Test Suite (`test-healing-scenarios.sh`)

**Purpose**: Interactive testing specifically for Phase 3 self-healing actions.

**Features**:
- ✅ Dry-run testing first
- ✅ Actual execution scenarios
- ✅ Safety mechanism validation
- ✅ Automatic resource cleanup

**Usage**:
```bash
./tests/test-healing-scenarios.sh
# Select option from menu (1-11)
```

**Test Scenarios**:
1. Test Pod Restart (Dry-Run)
2. Test Delete Failed Pods (Dry-Run)
3. Create & Delete Failing Pod (ACTUAL)
4. Test Deployment Scaling (Dry-Run)
5. Test Deployment Rollback (Dry-Run)
6. Create, Scale & Rollback Deployment (ACTUAL)
7. Test Node Cordon/Uncordon (Dry-Run)
8. View Healing Action History
9. Test Rate Limiting
10. Detection + Healing Integration Test
11. Run All Dry-Run Tests

---

### 4. Python Automated Tests (`test_healing_actions.py`)

**Purpose**: Automated unit and integration tests.

**Features**:
- ✅ Comprehensive test coverage
- ✅ Safety mechanism validation
- ✅ Automated assertions
- ✅ Integration testing

**Usage**:
```bash
python3 tests/test_healing_actions.py
```

**Test Coverage**:
- API health checks
- All healing actions (dry-run)
- Rate limiting validation
- Blast radius control
- Cooldown period enforcement
- Detection + Healing integration

---

## Test Categories

### Infrastructure Tests

**Purpose**: Validate foundational components.

**Tests**:
- Kubernetes cluster connectivity
- Namespace existence
- Deployment health
- Pod running status
- Service availability
- Prometheus health (optional)

**Run**:
```bash
./tests/run-all-tests.sh
# Automatically runs infrastructure tests first
```

---

### Observability Tests (Phase 1)

**Purpose**: Validate metric collection, logging, and tracing.

**Tests**:
- `get_metrics` - CPU usage
- `get_metrics` - Memory usage
- `get_metrics` - Network I/O
- `get_logs` - Recent logs
- `get_traces` - Distributed traces

**Run**:
```bash
# Via orchestrator
./tests/run-all-tests.sh

# Interactive
./tests/test-scenarios.sh
# Select options 1-4
```

---

### Detection Tests (Phase 2)

**Purpose**: Validate anomaly detection, pattern recognition, and health scoring.

**Tests**:
- `detect_anomalies` - CPU, Memory, Network
- `detect_patterns` - Error spikes, Restart loops
- `get_health_score` - Namespace and pod-level
- `analyze_correlations` - Multi-metric analysis
- `perform_rca` - Root cause analysis

**Run**:
```bash
# Via orchestrator
./tests/run-all-tests.sh

# Interactive
./tests/test-scenarios.sh
# Select options 5-11
```

---

### Healing Tests (Phase 3)

**Purpose**: Validate self-healing actions with safety controls.

**Tests**:
- `restart_pod` (Dry-run & Actual)
- `delete_failed_pods` (With blast radius)
- `scale_deployment` (Dynamic scaling)
- `rollback_deployment` (Version control)
- `cordon_node` / `uncordon_node`
- `get_healing_history` (Audit trail)

**Run**:
```bash
# Via orchestrator (all dry-run)
./tests/run-all-tests.sh

# Interactive scenarios
./tests/test-healing-scenarios.sh

# Automated Python tests
python3 tests/test_healing_actions.py
```

---

### Integration Tests

**Purpose**: Validate end-to-end workflows and cross-phase interactions.

**Tests**:
- Detection → Healing pipeline
- Multi-phase workflows
- Safety mechanism validation
- Rate limiting
- Blast radius control
- Dry-run verification

**Run**:
```bash
# Via orchestrator
./tests/run-all-tests.sh

# Interactive integration test
./tests/test-healing-scenarios.sh
# Select option 10
```

---

## Usage Examples

### Development Workflow

```bash
# 1. Make code changes
vim src/intelligent_sre_mcp/tools/healing_actions.py

# 2. Run quick validation
./tests/run-all-tests.sh -f  # Fail-fast mode

# 3. If tests pass, run full suite
./tests/run-all-tests.sh -v  # Verbose mode

# 4. Run specific interactive tests
./tests/test-healing-scenarios.sh
```

### Pre-Deployment Validation

```bash
# 1. Run complete test suite
./tests/run-all-tests.sh

# 2. Verify all phases pass
# Look for: "✓ ALL TESTS PASSED! 🎉"

# 3. Deploy to cluster
docker build -t intelligent-sre-agent:latest .
kubectl rollout restart deployment/intelligent-sre-agent -n intelligent-sre

# 4. Post-deployment validation
./tests/run-all-tests.sh
```

### Debugging Failed Tests

```bash
# 1. Run with verbose output
./tests/run-all-tests.sh -v

# 2. Check specific test category
./tests/test-scenarios.sh  # Select failing category

# 3. Check logs
kubectl logs -n intelligent-sre deployment/intelligent-sre-agent --tail=50

# 4. Check API server
curl http://localhost:30080/health
```

---

## CI/CD Integration

### GitHub Actions Example

```yaml
name: Test Intelligent SRE MCP

on: [push, pull_request]

jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      
      - name: Setup Kubernetes
        uses: engineerd/setup-kind@v0.5.0
      
      - name: Deploy Application
        run: |
          kubectl apply -f k8s/
          kubectl wait --for=condition=ready pod -l app=intelligent-sre-agent -n intelligent-sre --timeout=120s
      
      - name: Run Comprehensive Tests
        run: ./tests/run-all-tests.sh -v
      
      - name: Upload Test Results
        if: always()
        uses: actions/upload-artifact@v3
        with:
          name: test-results
          path: /tmp/test_output.log
```

### GitLab CI Example

```yaml
stages:
  - test

test_all:
  stage: test
  image: alpine/k8s:latest
  script:
    - kubectl apply -f k8s/
    - kubectl wait --for=condition=ready pod -l app=intelligent-sre-agent -n intelligent-sre --timeout=120s
    - ./tests/run-all-tests.sh -v
  artifacts:
    when: always
    paths:
      - /tmp/test_output.log
```

---

## Test Coverage Matrix

| Phase | Feature | Automated | Interactive | Safety Validated |
|-------|---------|-----------|-------------|------------------|
| **Phase 1: Observability** | | | | |
| | get_metrics | ✅ | ✅ | N/A |
| | get_logs | ✅ | ✅ | N/A |
| | get_traces | ✅ | ✅ | N/A |
| **Phase 2: Detection** | | | | |
| | detect_anomalies | ✅ | ✅ | N/A |
| | detect_patterns | ✅ | ✅ | N/A |
| | get_health_score | ✅ | ✅ | N/A |
| | analyze_correlations | ✅ | ✅ | N/A |
| | perform_rca | ✅ | ✅ | N/A |
| **Phase 3: Healing** | | | | |
| | restart_pod | ✅ | ✅ | ✅ |
| | delete_failed_pods | ✅ | ✅ | ✅ |
| | scale_deployment | ✅ | ✅ | ✅ |
| | rollback_deployment | ✅ | ✅ | ✅ |
| | cordon_node | ✅ | ✅ | ✅ |
| | uncordon_node | ✅ | ✅ | ✅ |
| | get_healing_history | ✅ | ✅ | N/A |
| **Safety Mechanisms** | | | | |
| | Rate limiting | ✅ | ✅ | ✅ |
| | Blast radius | ✅ | ✅ | ✅ |
| | Cooldown period | ✅ | ✅ | ✅ |
| | Dry-run mode | ✅ | ✅ | ✅ |
| | Audit logging | ✅ | ✅ | ✅ |

---

## Best Practices

### 1. Always Run Dry-Run First

```bash
# Before actual healing actions
./tests/run-all-tests.sh  # Runs all healing tests in dry-run mode
```

### 2. Use Fail-Fast During Development

```bash
# Stop on first error to save time
./tests/run-all-tests.sh -f
```

### 3. Verbose Output for Debugging

```bash
# See detailed output when investigating issues
./tests/run-all-tests.sh -v
```

### 4. Test After Every Code Change

```bash
# Quick validation
./tests/run-all-tests.sh -f

# Full validation before commit
./tests/run-all-tests.sh
```

### 5. Validate Safety Mechanisms

```bash
# Ensure safety controls work
./tests/test-healing-scenarios.sh
# Select option 9: Test Rate Limiting
```

---

## Troubleshooting

### Tests Failing?

1. **Check Prerequisites**:
   ```bash
   kubectl cluster-info
   curl http://localhost:30080/health
   ```

2. **Check Logs**:
   ```bash
   kubectl logs -n intelligent-sre deployment/intelligent-sre-agent --tail=50
   ```

3. **Verify Deployment**:
   ```bash
   kubectl get pods -n intelligent-sre
   kubectl get svc -n intelligent-sre
   ```

4. **Run Verbose Tests**:
   ```bash
   ./tests/run-all-tests.sh -v
   ```

### Common Issues

| Issue | Solution |
|-------|----------|
| API server not responding | Check pod status: `kubectl get pods -n intelligent-sre` |
| Rate limiting errors | Wait 1 hour or restart deployment |
| Dry-run tests failing | Check API endpoints: `curl http://localhost:30080/health` |
| Integration tests failing | Verify all phases work individually first |

---

## Summary

The Intelligent SRE MCP test suite provides:

✅ **Architecture-aligned testing** - Tests mirror the 3-phase application design  
✅ **Comprehensive coverage** - 45+ automated tests across all features  
✅ **Safety validation** - All safety mechanisms tested  
✅ **Multiple test modes** - Automated, interactive, and orchestrated  
✅ **CI/CD ready** - Easy integration with pipelines  
✅ **Developer-friendly** - Clear output and debugging tools

**Quick Start**: `./tests/run-all-tests.sh`

**Questions?** Check the logs: `kubectl logs -n intelligent-sre deployment/intelligent-sre-agent --tail=50`
