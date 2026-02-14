# Intelligent SRE MCP - Test Suite

This directory contains all testing tools and documentation for the Intelligent SRE MCP platform.

## 📁 Contents

- **`test_detection.py`** - Automated test suite (10 tests)
- **`test-scenarios.sh`** - Interactive test scenarios (9 scenarios)
- **`TESTING.md`** - Complete testing guide with detailed procedures
- **`TESTING_QUICKREF.md`** - Quick reference card for common tests

## 🚀 Quick Start

### Run All Automated Tests
```bash
python3 tests/test_detection.py
```

### Run Interactive Test Scenarios
```bash
./tests/test-scenarios.sh
```

### **🆕 End-to-End Test with Claude Desktop (Recommended)**
```bash
./tests/test-e2e-with-claude.sh
```

**This is the most comprehensive test that:**
- ✅ Deploys all test infrastructure (7 pods with various failures)
- ⏱️ Waits for issues to develop in metrics
- 🔍 Shows detection results (anomalies, patterns, correlations)
- 🤖 Gives you time to test with Claude Desktop
- 🧹 Automatically cleans up when done

**Perfect for:**
- Demo purposes
- Verifying Claude Desktop integration
- Testing all detection engines at once
- Showing stakeholders the full capability

## 📋 Test Categories

### 1. Automated Tests (`test_detection.py`)
- ✓ API Health Check
- ✓ Prometheus Connection
- ✓ Kubernetes API Connection
- ✓ Anomaly Detection
- ✓ Health Score Calculation
- ✓ Pattern Recognition
- ✓ Correlation Analysis
- ✓ Comprehensive Analysis
- ✓ Metric Spike Detection
- ✓ Prometheus Targets Health

**Usage:**
```bash
cd /Users/sanket/Desktop/intelligent-sre-mcp
python3 tests/test_detection.py
```

**Expected Output:**
```
========================================
Intelligent SRE MCP - Test Suite
========================================
Phase 1: Basic Connectivity
✓ API is healthy: healthy
✓ Kubernetes API is accessible (9 pods found)
...
Pass Rate: 80.0%
```

---

### 2. Interactive Scenarios (`test-scenarios.sh`)

**Menu-driven interface with 9 scenarios:**

1. **Baseline Health Check** - Test current system without issues
2. **High CPU Usage** - Simulate CPU stress with stress-test pod
3. **High Memory Usage** - Simulate memory pressure
4. **Crash Loop** - Create crashing pod (tests restart detection)
5. **Image Pull Error** - Test ImagePullBackOff detection
6. **Cascading Failure** - Multiple failing pods (tests correlation)
7. **Comprehensive Analysis** - Full system scan
8. **Metric Spike Detection** - Custom metric monitoring
9. **Claude Desktop Test** - Integration test prompts
10. **Run All Scenarios** - Execute all sequentially (15-20 min)
11. **🆕 End-to-End Test with Claude** - Complete workflow (Recommended)

**Usage:**
```bash
cd /Users/sanket/Desktop/intelligent-sre-mcp
./tests/test-scenarios.sh
```

---

## 🎯 Test What Each Scenario Validates

| Scenario | Component Tested | Detection Engine |
|----------|-----------------|------------------|
| Baseline | API, K8s, Prometheus | Health Score |
| CPU Stress | Anomaly Detection | Z-score analysis |
| Memory Pressure | Anomaly Detection | Threshold detection |
| Crash Loop | Pattern Recognition | Recurring failures |
| Image Pull | Anomaly Detection | Pending pods |
| Cascading Failure | Correlation Engine | Multi-pod correlation |
| Comprehensive | All Detection Engines | Combined analysis |
| Metric Spike | Spike Detection | Historical comparison |
| Claude Desktop | MCP Integration | All 17 tools |

---

## 📊 Expected Results by Scenario

### Healthy System (Baseline)
```json
{
  "health_score": 90-100,
  "status": "healthy",
  "total_anomalies": 0,
  "total_patterns": 0,
  "total_correlations": 0
}
```

### High CPU/Memory Usage
```json
{
  "health_score": 50-70,
  "status": "unhealthy",
  "cpu_anomalies": 1+,
  "recommendations": ["Investigate high CPU usage"]
}
```

### Crash Loop
```json
{
  "health_score": 0-50,
  "status": "critical",
  "restart_anomalies": 1+,
  "patterns": {
    "recurring_failures": 1+
  }
}
```

### Cascading Failures
```json
{
  "health_score": 0-50,
  "status": "critical",
  "correlations": {
    "cascading_failures": 1+
  }
}
```

---

## 🧪 Creating Custom Test Scenarios

### Example: Test Custom Metric
```bash
# In tests/test-scenarios.sh, add new function:
scenario_custom_test() {
    print_header "Custom Test Scenario"
    
    # Your test code here
    kubectl apply -f custom-pod.yaml
    sleep 30
    curl "http://localhost:30080/detection/anomalies" | python3 -m json.tool
    
    kubectl delete -f custom-pod.yaml
}
```

### Example: Test Specific Namespace
```bash
# Test different namespace
curl "http://localhost:30080/detection/comprehensive?namespace=kube-system" | python3 -m json.tool
```

---

## 🔍 Testing with Claude Desktop

### Setup
1. Ensure Claude Desktop is configured (see main README.md)
2. Restart Claude: `killall Claude && open -a Claude`

### Test Prompts
Copy these into Claude Desktop:

```
1. "What's the health score of my intelligent-sre namespace?"
2. "Detect all anomalies in my cluster"
3. "Show me patterns in pod failures"
4. "Are there any correlations between restarts and events?"
5. "Run comprehensive analysis on intelligent-sre namespace"
6. "Which pods are failing and why?"
7. "Detect CPU spikes in the last hour"
8. "Is my system healthy?"
```

### Expected Claude Behavior
- Claude should invoke MCP tools (detect_anomalies, get_health_score, etc.)
- Responses include real data from your cluster
- Health scores, anomaly counts, and recommendations displayed
- Claude can chain multiple tools for complex queries

---

## 📈 Performance Benchmarks

| Endpoint | Expected Response Time |
|----------|----------------------|
| `/health` | < 50ms |
| `/k8s/pods` | < 500ms |
| `/detection/anomalies` | < 2s |
| `/detection/health-score` | < 2s |
| `/detection/patterns` | < 3s |
| `/detection/correlations` | < 3s |
| `/detection/comprehensive` | < 5s |

If response times exceed these thresholds:
1. Check Prometheus query performance
2. Verify Kubernetes API latency
3. Review pod resource limits

---

## 🐛 Troubleshooting Tests

### Test Fails: "Connection refused"
```bash
# Check if API pod is running
kubectl get pods -n intelligent-sre | grep intelligent-sre-mcp

# View API logs
kubectl logs -n intelligent-sre deployment/intelligent-sre-mcp

# Port forward if needed
kubectl port-forward -n intelligent-sre svc/intelligent-sre-mcp-service 30080:80
```

### Test Fails: "Prometheus not reachable"
```bash
# Check Prometheus pod
kubectl get pods -n intelligent-sre | grep prometheus

# View Prometheus logs
kubectl logs -n intelligent-sre deployment/prometheus

# Test Prometheus directly
curl http://localhost:30090/api/v1/query?query=up
```

### Test Fails: "403 Forbidden"
```bash
# Verify RBAC is configured
kubectl get clusterrole intelligent-sre-mcp-role
kubectl get clusterrolebinding intelligent-sre-mcp-binding

# Reapply RBAC if needed
kubectl apply -f k8s/rbac.yaml
```

### Tests Pass but Claude Desktop Doesn't Work
```bash
# Check Claude config
cat ~/Library/Application\ Support/Claude/claude_desktop_config.json

# Restart Claude completely
killall Claude
open -a Claude

# Check MCP wrapper script
cat setup/run_mcp_api.sh

# Test API manually
curl http://localhost:30080/health
```

---

## 📝 Test Checklist Before Production

- [ ] All automated tests pass (10/10)
- [ ] All interactive scenarios tested
- [ ] Claude Desktop integration verified
- [ ] All pods in Running state
- [ ] Prometheus scraping 5+ targets
- [ ] Health score calculates correctly
- [ ] Anomalies detected during stress tests
- [ ] Patterns recognized after repeated failures
- [ ] Correlations found during cascading failures
- [ ] Comprehensive analysis returns all sections
- [ ] Response times within benchmarks
- [ ] RBAC permissions working
- [ ] Alert rules active in Prometheus

---

## 🔗 Documentation Links

- **[TESTING.md](TESTING.md)** - Complete testing guide
- **[TESTING_QUICKREF.md](TESTING_QUICKREF.md)** - Quick reference card
- **[../README.md](../README.md)** - Main project documentation
- **[../k8s/alert_rules.yaml](../k8s/alert_rules.yaml)** - Prometheus alert rules

---

## 🤝 Contributing Tests

To add new tests:

1. **Automated Tests**: Add test methods to `test_detection.py`
2. **Interactive Scenarios**: Add scenario functions to `test-scenarios.sh`
3. **Documentation**: Update this README and TESTING.md
4. **Verify**: Run `python3 tests/test_detection.py` to ensure all pass

---

## 📊 Current Test Coverage

- **API Endpoints**: 13/13 (100%)
- **MCP Tools**: 17/17 (100%)
- **Detection Engines**: 3/3 (100%)
- **Kubernetes Resources**: Pods, Nodes, Deployments, Events
- **Prometheus Metrics**: CPU, Memory, Restarts, Custom queries
- **Alert Rules**: 20+ rules tested via scenarios

---

For quick commands and common test patterns, see **[TESTING_QUICKREF.md](TESTING_QUICKREF.md)**.
