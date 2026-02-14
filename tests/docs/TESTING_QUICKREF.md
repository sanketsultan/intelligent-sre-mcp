# Quick Testing Reference

## 🚀 Quick Start

```bash
# Automated tests (recommended)
python3 test_detection.py

# Interactive scenarios
./test-scenarios.sh
```

---

## 📋 Test Checklist

| Test | Command | Expected Result |
|------|---------|----------------|
| API Health | `curl http://localhost:30080/health` | `{"status": "healthy"}` |
| Anomalies | `curl http://localhost:30080/detection/anomalies?namespace=intelligent-sre` | Anomaly count |
| Health Score | `curl http://localhost:30080/detection/health-score` | Score 0-100 |
| Patterns | `curl http://localhost:30080/detection/patterns` | Pattern list |
| Correlations | `curl http://localhost:30080/detection/correlations` | Correlation list |
| Comprehensive | `curl http://localhost:30080/detection/comprehensive` | Full analysis |

---

## 🎯 Test Scenarios

### 1. CPU Stress Test
```bash
kubectl apply -f - <<EOF
apiVersion: v1
kind: Pod
metadata:
  name: cpu-stress
  namespace: intelligent-sre
spec:
  containers:
  - name: stress
    image: progrium/stress
    args: ["--cpu", "2", "--timeout", "300s"]
EOF

# Wait 30s, then check
curl http://localhost:30080/detection/anomalies?namespace=intelligent-sre | python3 -m json.tool

# Cleanup
kubectl delete pod cpu-stress -n intelligent-sre
```

### 2. Crash Loop Test
```bash
kubectl apply -f - <<EOF
apiVersion: v1
kind: Pod
metadata:
  name: crash-test
  namespace: intelligent-sre
spec:
  restartPolicy: Always
  containers:
  - name: crasher
    image: busybox
    command: ["/bin/sh", "-c", "sleep 5; exit 1"]
EOF

# Wait 2 minutes for crashes
sleep 120

# Check patterns
curl http://localhost:30080/detection/patterns?namespace=intelligent-sre | python3 -m json.tool

# Cleanup
kubectl delete pod crash-test -n intelligent-sre
```

### 3. Cascading Failures
```bash
# Create 3 failing pods
for i in 1 2 3; do
  kubectl apply -f - <<EOF
apiVersion: v1
kind: Pod
metadata:
  name: cascade-$i
  namespace: intelligent-sre
spec:
  restartPolicy: Always
  containers:
  - name: fail
    image: busybox
    command: ["/bin/sh", "-c", "sleep $i; exit 1"]
EOF
done

# Wait 1 minute
sleep 60

# Check correlations
curl http://localhost:30080/detection/correlations?namespace=intelligent-sre | python3 -m json.tool

# Cleanup
kubectl delete pod cascade-1 cascade-2 cascade-3 -n intelligent-sre
```

---

## 🔍 Claude Desktop Test Prompts

Copy these into Claude Desktop:

```
1. "What's the health score of my cluster?"
2. "Detect all anomalies in intelligent-sre namespace"
3. "Show me patterns in pod failures"
4. "Are there any correlations between restarts and events?"
5. "Run comprehensive analysis"
6. "Which pods are failing and why?"
7. "Is my system healthy?"
```

---

## 📊 Expected Results

| Scenario | Health Score | Anomalies | Patterns | Correlations |
|----------|-------------|-----------|----------|--------------|
| Healthy | 90-100 ✅ | 0 | 0 | 0 |
| High CPU/Memory | 50-70 ⚠️ | 1+ | 0 | 0 |
| Crash Loop | 0-50 🔥 | 1+ | 1+ | 0-1 |
| Cascading | 0-50 🔥 | 3+ | 1+ | 1+ |

---

## 🐛 Troubleshooting

| Problem | Check | Fix |
|---------|-------|-----|
| Connection refused | `kubectl get pods -n intelligent-sre` | Restart pod |
| 403 Forbidden | `kubectl get clusterrole` | Apply RBAC |
| Empty results | `curl http://localhost:30080/health` | Check API |
| Claude not working | Check config file | Restart Claude |

---

## 📈 Performance Benchmarks

| Endpoint | Expected Time |
|----------|--------------|
| `/health` | < 50ms |
| `/detection/anomalies` | < 2s |
| `/detection/patterns` | < 3s |
| `/detection/correlations` | < 3s |
| `/detection/comprehensive` | < 5s |

---

## 🔧 Quick Commands

```bash
# View all pods
kubectl get pods -n intelligent-sre

# View API logs
kubectl logs -n intelligent-sre deployment/intelligent-sre-mcp

# View Prometheus logs
kubectl logs -n intelligent-sre deployment/prometheus

# Port forward (if needed)
kubectl port-forward -n intelligent-sre svc/intelligent-sre-mcp-service 30080:80

# Restart deployment
kubectl rollout restart -n intelligent-sre deployment/intelligent-sre-mcp

# Delete test pods
kubectl delete pod -n intelligent-sre -l app=stress-test
kubectl delete pod -n intelligent-sre -l app=crash-test
kubectl delete pod -n intelligent-sre -l app=cascade-test
```

---

For full details, see **[TESTING.md](TESTING.md)**
