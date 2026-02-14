# Intelligent SRE MCP - Test Suite

Complete testing suite for validating all detection engines and Claude Desktop integration.

## 🚀 Quick Start

### Recommended: End-to-End Test
```bash
./tests/test-e2e-with-claude.sh
```
**Best for:** Demos, full validation, Claude Desktop testing

### Alternative: Menu-Driven Tests
```bash
./tests/test-scenarios.sh
```
**Best for:** Testing specific scenarios

### Automated Tests
```bash
python3 tests/test_detection.py
```
**Best for:** CI/CD, quick validation

---

## 📋 Test Scripts

| Script | Purpose | Duration |
|--------|---------|----------|
| `test-e2e-with-claude.sh` | Complete end-to-end test with automatic cleanup | 5-10 min + your testing time |
| `test-scenarios.sh` | Interactive menu with 11 test scenarios | Varies by scenario |
| `test_detection.py` | Automated test suite (10 tests) | ~30 seconds |

---

## 🎯 What Each Test Does

### 1. End-to-End Test (★ Recommended)
**File:** `test-e2e-with-claude.sh`

**Deploys:**
- 7 test pods (CPU stress, memory stress, crash loops, cascading failures)
- Waits for issues to develop
- Shows detection results
- Time for Claude Desktop testing
- Automatic cleanup

**Perfect for:**
- Demos to stakeholders
- Validating all features
- Testing Claude Desktop integration

### 2. Interactive Scenarios
**File:** `test-scenarios.sh`

**11 scenarios:**
1. Baseline Health Check
2. High CPU Usage
3. High Memory Usage
4. Crash Loop
5. Image Pull Error
6. Cascading Failure
7. Comprehensive Analysis
8. Metric Spike Detection
9. Claude Desktop Integration
10. Run All Scenarios
11. End-to-End Test (launches test-e2e-with-claude.sh)

### 3. Automated Tests
**File:** `test_detection.py`

**10 tests:**
- API health check
- Prometheus connection
- Kubernetes API connection
- Anomaly detection
- Health score calculation
- Pattern recognition
- Correlation analysis
- Comprehensive analysis
- Metric spike detection
- Prometheus targets health

**Current pass rate:** 80% (8/10)

---

## 📊 Expected Results

### Healthy System (No Issues)
```
Health Score: 90-100 ✅
Anomalies: 0
Patterns: 0
Correlations: 0
```

### During E2E Test (Issues Injected)
```
Health Score: 0-50 🔥 (Critical)
Anomalies: 5-7
  • CPU: 1-2
  • Memory: 1-2
  • Restarts: 1
  • Pending: 1
Patterns: 1-2
Correlations: 1-2
```

---

## 🤖 Testing with Claude Desktop

When running the E2E test, try these prompts in Claude Desktop:

**Basic:**
- "What is the health score of intelligent-sre?"
- "Is my system healthy?"

**Anomalies:**
- "Detect all anomalies in intelligent-sre namespace"
- "Show me pods with high restart counts"

**Patterns:**
- "Show me patterns in pod failures"
- "Are there any recurring issues?"

**Correlations:**
- "Are there any cascading failures?"
- "What is causing the pod failures?"

**Comprehensive:**
- "Run comprehensive analysis on intelligent-sre"
- "Give me a full system report"

---

## 📚 Documentation

All detailed documentation is in the `docs/` subdirectory:

- **[docs/E2E_TEST_GUIDE.md](docs/E2E_TEST_GUIDE.md)** - Complete E2E test guide
- **[docs/E2E_QUICKREF.txt](docs/E2E_QUICKREF.txt)** - E2E quick reference card
- **[docs/TESTING.md](docs/TESTING.md)** - Comprehensive testing guide
- **[docs/TESTING_QUICKREF.md](docs/TESTING_QUICKREF.md)** - General quick reference
- **[docs/README.md](docs/README.md)** - Original detailed README

---

## 🧹 Cleanup

All test scripts handle cleanup automatically:
- E2E test: Automatic via EXIT trap
- Scenarios: Manual cleanup prompts
- Automated: No cleanup needed (read-only)

**Manual cleanup if needed:**
```bash
kubectl delete pods -n intelligent-sre -l app=e2e-test --force --grace-period=0
```

---

## 🐛 Troubleshooting

| Issue | Solution |
|-------|----------|
| Connection refused | `kubectl get pods -n intelligent-sre` |
| Pods not creating | Check RBAC: `kubectl get clusterrole intelligent-sre-mcp-role` |
| No anomalies detected | Wait 60s for metrics to populate |
| Claude not working | Restart: `killall Claude && open -a Claude` |

---

## ✅ Test Coverage

- **API Endpoints:** 13/13 (100%)
- **MCP Tools:** 17/17 (100%)
- **Detection Engines:** 3/3 (100%)
- **Kubernetes Resources:** Pods, Nodes, Deployments, Events
- **Prometheus Metrics:** CPU, Memory, Restarts, Custom queries

---

**For detailed information, see [docs/](docs/) directory.**
