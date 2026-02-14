# Testing Guide for Intelligent SRE MCP

This guide provides comprehensive instructions for testing all features of the Intelligent SRE MCP platform.

## Quick Start

### 1. Automated Test Suite (Recommended)
Run the automated Python test suite to verify all detection engines:

```bash
python3 test_detection.py
```

**What it tests:**
- ✓ API health and connectivity
- ✓ Prometheus connection
- ✓ Kubernetes API access
- ✓ Anomaly detection engine
- ✓ Health score calculation
- ✓ Pattern recognition
- ✓ Correlation analysis
- ✓ Comprehensive analysis
- ✓ Metric spike detection
- ✓ Prometheus targets health

**Expected output:**
```
========================================
Intelligent SRE MCP - Test Suite
========================================

Phase 1: Basic Connectivity
✓ API is healthy: healthy
✓ Prometheus is reachable and responding
✓ Kubernetes API is accessible (8 pods found)
...

Test Summary
✓ All tests passed!
Pass Rate: 100%
```

---

### 2. Interactive Test Scenarios
Run interactive scenarios to test specific failure conditions:

```bash
./test-scenarios.sh
```

**Available scenarios:**

1. **Baseline Health Check** - Test current system without issues
2. **High CPU Usage** - Simulate CPU stress (creates stress-test pod)
3. **High Memory Usage** - Simulate memory pressure
4. **Crash Loop** - Create pod that crashes repeatedly (tests restart detection)
5. **Image Pull Error** - Test ImagePullBackOff detection
6. **Cascading Failure** - Multiple pods failing (tests correlation)
7. **Comprehensive Analysis** - Full system analysis
8. **Metric Spike Detection** - Custom metric monitoring
9. **Claude Desktop Test** - Integration test prompts
10. **Run All** - Execute all scenarios sequentially

---

## Testing Individual Components

### Test Prometheus Connection
```bash
curl "http://localhost:30090/api/v1/query?query=up" | python3 -m json.tool
```

**Expected:** List of scrape targets with `value: ["timestamp", "1"]`

### Test API Health
```bash
curl http://localhost:30080/health
```

**Expected:** `{"status": "healthy"}`

### Test Anomaly Detection
```bash
curl "http://localhost:30080/detection/anomalies?namespace=intelligent-sre" | python3 -m json.tool
```

**Expected:**
```json
{
  "namespace": "intelligent-sre",
  "total_anomalies": 0,
  "critical_anomalies": 0,
  "warning_anomalies": 0,
  "cpu_anomalies": [],
  "memory_anomalies": [],
  "restart_anomalies": [],
  "pending_pod_anomalies": []
}
```

### Test Health Score
```bash
curl "http://localhost:30080/detection/health-score?namespace=intelligent-sre" | python3 -m json.tool
```

**Expected:**
```json
{
  "health_score": 100,
  "status": "healthy",
  "status_emoji": "✅",
  "total_anomalies": 0,
  "critical": 0,
  "warning": 0,
  "recommendations": ["System is operating normally"]
}
```

### Test Pattern Recognition
```bash
curl "http://localhost:30080/detection/patterns?namespace=intelligent-sre" | python3 -m json.tool
```

**Expected:**
```json
{
  "namespace": "intelligent-sre",
  "total_patterns": 0,
  "recurring_failures": [],
  "cyclic_spikes": [],
  "resource_exhaustion": [],
  "cascading_failures": [],
  "deployment_issues": [],
  "insights": ["✅ No problematic patterns detected"]
}
```

### Test Correlation Analysis
```bash
curl "http://localhost:30080/detection/correlations?namespace=intelligent-sre" | python3 -m json.tool
```

**Expected:**
```json
{
  "namespace": "intelligent-sre",
  "total_correlations": 0,
  "restart_event_correlations": [],
  "cpu_event_correlations": [],
  "memory_oom_correlations": [],
  "insights": ["✅ No significant correlations detected"]
}
```

### Test Comprehensive Analysis
```bash
curl "http://localhost:30080/detection/comprehensive?namespace=intelligent-sre" | python3 -m json.tool
```

**Expected:** Combined output with health_score, anomalies, patterns, and correlations

### Test Metric Spike Detection
```bash
# CPU spike detection
curl "http://localhost:30080/detection/spike?query=sum(rate(container_cpu_usage_seconds_total[5m]))%20by%20(pod)%20*%20100&duration=1h&spike_multiplier=2.0" | python3 -m json.tool

# Memory spike detection
curl "http://localhost:30080/detection/spike?query=sum(container_memory_working_set_bytes)%20by%20(pod)&duration=1h&spike_multiplier=1.5" | python3 -m json.tool
```

---

## Testing Claude Desktop Integration

### 1. Verify MCP Configuration
Check that Claude Desktop is configured:
```bash
cat ~/Library/Application\ Support/Claude/claude_desktop_config.json
```

**Expected:**
```json
{
  "mcpServers": {
    "intelligent-sre-mcp": {
      "command": "/Users/YOUR_USERNAME/Desktop/intelligent-sre-mcp/run_mcp_api.sh",
      "args": [],
      "env": {
        "API_URL": "http://localhost:30080"
      }
    }
  }
}
```

### 2. Restart Claude Desktop
```bash
killall Claude
open -a Claude
```

### 3. Test with Natural Language Prompts

Open Claude Desktop and try these prompts:

#### Basic Health Checks
- "What's the health score of my intelligent-sre namespace?"
- "Is my system healthy?"
- "Show me the status of all pods"

#### Anomaly Detection
- "Detect all anomalies in intelligent-sre namespace"
- "Are there any CPU or memory anomalies?"
- "Show me pods with high restart counts"
- "Detect anomalies across the entire cluster"

#### Pattern Recognition
- "Show me patterns in pod failures"
- "Are there any recurring issues?"
- "Detect cyclic CPU spikes"
- "Find resource exhaustion trends"

#### Correlation Analysis
- "Show correlations between restarts and events"
- "Correlate CPU spikes with deployment activities"
- "Are there any cascading failures?"
- "Find the root cause of pod failures"

#### Comprehensive Analysis
- "Run comprehensive analysis on intelligent-sre namespace"
- "Give me a full system report"
- "Analyze my entire cluster health"

#### Custom Metrics
- "Detect CPU spikes in the last hour"
- "Show me memory usage trends"
- "Are there any sudden metric increases?"

#### Troubleshooting
- "Which pods are failing and why?"
- "Show me logs from the prometheus pod"
- "What events happened recently?"
- "Describe the grafana pod in detail"

---

## Creating Test Scenarios

### Scenario 1: High CPU Usage
```bash
cat <<EOF | kubectl apply -f -
apiVersion: v1
kind: Pod
metadata:
  name: cpu-stress-test
  namespace: intelligent-sre
spec:
  containers:
  - name: cpu-stress
    image: progrium/stress
    args: ["--cpu", "2", "--timeout", "300s"]
    resources:
      limits:
        cpu: "500m"
      requests:
        cpu: "250m"
EOF

# Wait 30 seconds, then test
sleep 30
curl "http://localhost:30080/detection/anomalies?namespace=intelligent-sre" | python3 -m json.tool

# Cleanup
kubectl delete pod cpu-stress-test -n intelligent-sre
```

**Expected:** CPU anomalies detected

---

### Scenario 2: Memory Pressure
```bash
cat <<EOF | kubectl apply -f -
apiVersion: v1
kind: Pod
metadata:
  name: memory-stress-test
  namespace: intelligent-sre
spec:
  containers:
  - name: memory-stress
    image: progrium/stress
    args: ["--vm", "1", "--vm-bytes", "100M", "--timeout", "300s"]
    resources:
      limits:
        memory: "128Mi"
      requests:
        memory: "64Mi"
EOF

# Wait 30 seconds, then test
sleep 30
curl "http://localhost:30080/detection/anomalies?namespace=intelligent-sre" | python3 -m json.tool

# Cleanup
kubectl delete pod memory-stress-test -n intelligent-sre
```

**Expected:** Memory anomalies detected

---

### Scenario 3: Crash Loop
```bash
cat <<EOF | kubectl apply -f -
apiVersion: v1
kind: Pod
metadata:
  name: crash-loop-test
  namespace: intelligent-sre
spec:
  restartPolicy: Always
  containers:
  - name: crash-container
    image: busybox
    command: ["/bin/sh", "-c", "sleep 5; exit 1"]
EOF

# Wait 2 minutes for multiple crashes
sleep 120
curl "http://localhost:30080/detection/anomalies?namespace=intelligent-sre" | python3 -m json.tool
curl "http://localhost:30080/detection/patterns?namespace=intelligent-sre" | python3 -m json.tool

# Cleanup
kubectl delete pod crash-loop-test -n intelligent-sre
```

**Expected:** 
- Restart anomalies detected
- Recurring failure pattern detected

---

### Scenario 4: Cascading Failures
```bash
# Create multiple failing pods
for i in 1 2 3; do
  cat <<EOF | kubectl apply -f -
apiVersion: v1
kind: Pod
metadata:
  name: cascade-test-$i
  namespace: intelligent-sre
spec:
  restartPolicy: Always
  containers:
  - name: failing-container
    image: busybox
    command: ["/bin/sh", "-c", "sleep $((i * 5)); exit 1"]
EOF
done

# Wait 1 minute
sleep 60
curl "http://localhost:30080/detection/correlations?namespace=intelligent-sre" | python3 -m json.tool

# Cleanup
kubectl delete pod cascade-test-1 cascade-test-2 cascade-test-3 -n intelligent-sre
```

**Expected:** Cascading failure correlation detected

---

## Expected Results by Scenario

### Healthy System (Baseline)
- Health Score: **90-100** ✅
- Status: **healthy**
- Anomalies: **0**
- Patterns: **0**
- Correlations: **0**

### High CPU Usage
- Health Score: **50-70** ⚠️
- Status: **unhealthy**
- CPU Anomalies: **1+**
- Recommendations: "Investigate high CPU usage"

### High Memory Usage
- Health Score: **50-70** ⚠️
- Status: **unhealthy**
- Memory Anomalies: **1+**
- Recommendations: "Monitor memory consumption"

### Crash Loop
- Health Score: **0-50** 🔥
- Status: **critical**
- Restart Anomalies: **1+**
- Patterns: **recurring_failures** detected
- Recommendations: "Fix crash loop in pod"

### Cascading Failures
- Health Score: **0-50** 🔥
- Status: **critical**
- Correlations: **cascading_failures** detected
- Recommendations: "Investigate systemic issues"

---

## Troubleshooting Tests

### Test Fails: "Connection refused"
**Problem:** API is not running
**Solution:**
```bash
kubectl get pods -n intelligent-sre | grep intelligent-sre-mcp
kubectl logs -n intelligent-sre deployment/intelligent-sre-mcp
```

### Test Fails: "Prometheus not reachable"
**Problem:** Prometheus is down
**Solution:**
```bash
kubectl get pods -n intelligent-sre | grep prometheus
kubectl logs -n intelligent-sre deployment/prometheus
```

### Test Fails: "Forbidden (403)"
**Problem:** RBAC permissions missing
**Solution:**
```bash
kubectl get clusterrole intelligent-sre-mcp-role
kubectl get clusterrolebinding intelligent-sre-mcp-binding
kubectl apply -f k8s/rbac.yaml
```

### Claude Desktop Not Showing MCP Tools
**Problem:** Configuration error
**Solution:**
1. Check config: `cat ~/Library/Application\ Support/Claude/claude_desktop_config.json`
2. Restart Claude: `killall Claude && open -a Claude`
3. Check logs: Look for errors in Claude Desktop console

---

## Performance Benchmarks

Expected response times (on local K8s):
- `/health`: < 50ms
- `/prometheus/query`: < 500ms
- `/k8s/pods`: < 500ms
- `/detection/anomalies`: < 2s
- `/detection/health-score`: < 2s
- `/detection/patterns`: < 3s
- `/detection/correlations`: < 3s
- `/detection/comprehensive`: < 5s

If response times exceed these thresholds, check:
1. Prometheus query performance
2. Kubernetes API latency
3. Pod resource limits

---

## Continuous Testing

### Run Tests on Schedule
Add to crontab to run tests every hour:
```bash
0 * * * * cd /Users/YOUR_USERNAME/Desktop/intelligent-sre-mcp && python3 test_detection.py >> /tmp/sre-tests.log 2>&1
```

### Monitor Test Results
```bash
tail -f /tmp/sre-tests.log
```

---

## Test Checklist

Before deploying to production, verify:

- [ ] Automated test suite passes (100%)
- [ ] All 9 interactive scenarios work
- [ ] Claude Desktop integration functional
- [ ] Prometheus scraping 5 targets
- [ ] All pods in Running state
- [ ] Health score calculates correctly
- [ ] Anomalies detected during stress tests
- [ ] Patterns recognized after multiple failures
- [ ] Correlations found during cascading failures
- [ ] Comprehensive analysis returns all sections
- [ ] Response times within benchmarks
- [ ] RBAC permissions working
- [ ] Alert rules firing in Prometheus

---

## Additional Resources

- **API Documentation**: Check `/detection/` endpoints in `src/intelligent_sre_mcp/api_server.py`
- **Detection Logic**: Review `tools/anomaly_detection.py`, `tools/pattern_recognition.py`, `tools/correlation.py`
- **Prometheus Queries**: See PromQL patterns in detection modules
- **Alert Rules**: Check `k8s/alert_rules.yaml` for threshold definitions

---

## Support

If tests fail consistently:
1. Check pod logs: `kubectl logs -n intelligent-sre <pod-name>`
2. Verify services: `kubectl get svc -n intelligent-sre`
3. Test endpoints manually with curl
4. Review detection module code for logic errors
5. Check Prometheus for data availability
