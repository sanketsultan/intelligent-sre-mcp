# End-to-End Test with Claude Desktop

## Overview

This is a **comprehensive, automated test** that deploys real failure scenarios, lets you verify with Claude Desktop, and automatically cleans up.

## What It Does

### 1. Baseline Check (30 seconds)
- Checks API health
- Records baseline health score
- Counts current anomalies

### 2. Deploy Test Infrastructure (1 minute)
Creates 7 test pods:
- **cpu-stress-test** - High CPU usage (2 cores stress)
- **memory-stress-test** - High memory usage (100MB)
- **crash-loop-test** - Pod that crashes every 10 seconds
- **image-pull-test** - ImagePullBackOff error
- **cascade-test-1, 2, 3** - Cascading failures (3 pods)

### 3. Wait for Issues (2 minutes)
Countdown timer while:
- Metrics populate in Prometheus
- Crash loop restarts multiple times
- Cascading failures propagate
- Anomalies become detectable

### 4. Show Detection Results (1 minute)
Displays:
- Current pod status
- Detected anomalies (CPU, memory, restarts, pending)
- Health score (should be critical: 0-50)
- Patterns (recurring failures)
- Correlations (cascading failures)

### 5. Claude Desktop Testing (Your time!)
Provides 20+ test prompts including:
- "What is the health score?"
- "Detect all anomalies"
- "Show me patterns in pod failures"
- "Are there any cascading failures?"
- "Run comprehensive analysis"

### 6. Final State Check (30 seconds)
- Shows final health score
- Compares to baseline
- Lists all test pods

### 7. Automatic Cleanup
- Deletes all 7 test pods
- Verifies cleanup complete
- System returns to baseline

---

## Usage

```bash
./tests/test-e2e-with-claude.sh
```

**That's it!** The script is fully automated with prompts at key points.

---

## What to Expect

### Before Test (Healthy System)
```
Health Score: 90-100 ✅
Anomalies: 0
Patterns: 0
Correlations: 0
```

### During Test (Issues Injected)
```
Health Score: 0-50 🔥 (Critical)
Anomalies: 5-7
  • CPU anomalies: 1-2
  • Memory anomalies: 1-2
  • Restart anomalies: 1
  • Pending pod anomalies: 1
Patterns: 1-2
  • Recurring failures detected
  • Cascading failures detected
Correlations: 1-2
  • Restarts ↔ Events
  • Cascading failures
```

### After Test (Cleaned Up)
```
Health Score: 90-100 ✅
Anomalies: 0
Patterns: 0
Correlations: 0
```

---

## Claude Desktop Test Prompts

### Basic Health
```
"What is the health score of my intelligent-sre namespace?"
"Is my system healthy?"
"Show me all pods in intelligent-sre namespace"
```

**Expected:** Claude uses `get_health_score()`, shows critical status

### Anomaly Detection
```
"Detect all anomalies in intelligent-sre namespace"
"Are there any CPU or memory anomalies?"
"Show me pods with high restart counts"
"Which pods are pending and why?"
```

**Expected:** Claude uses `detect_anomalies()`, shows 5-7 anomalies

### Pattern Recognition
```
"Show me patterns in pod failures"
"Are there any recurring issues?"
"Detect cyclic problems in my cluster"
```

**Expected:** Claude uses `detect_patterns()`, identifies recurring failures

### Correlation Analysis
```
"Show correlations between restarts and events"
"Are there any cascading failures?"
"What is causing the pod failures?"
```

**Expected:** Claude uses `detect_correlations()`, finds cascading failures

### Comprehensive
```
"Run comprehensive analysis on intelligent-sre namespace"
"Give me a full system report"
"What issues should I be concerned about?"
```

**Expected:** Claude uses `comprehensive_analysis()`, provides full report

### Troubleshooting
```
"Which pods are failing and why?"
"Show me logs from crash-loop-test pod"
"Describe the cpu-stress-test pod"
"What events happened recently?"
```

**Expected:** Claude uses K8s tools, shows logs and pod details

---

## Timeline

| Phase | Duration | What Happens |
|-------|----------|--------------|
| Baseline Check | 30s | Record healthy state |
| Deploy Infra | 1m | Create 7 test pods |
| Wait for Issues | 2m | Countdown timer |
| Show Results | 1m | Display detection results |
| **Claude Testing** | **Your time!** | **Test all prompts** |
| Final Check | 30s | Compare to baseline |
| Cleanup | 30s | Delete test pods |
| **Total** | **~6-10 minutes** | **Plus your testing time** |

---

## Cleanup

**Automatic!** Cleanup happens when:
- You press Enter after testing
- You press Ctrl+C to exit
- Script completes normally

The script uses a trap to ensure cleanup always runs:
```bash
trap cleanup_test_pods EXIT
```

**To verify cleanup:**
```bash
kubectl get pods -n intelligent-sre -l app=e2e-test
# Should show: No resources found
```

---

## Troubleshooting

### Pods not creating
```bash
# Check namespace exists
kubectl get namespace intelligent-sre

# Check RBAC permissions
kubectl auth can-i create pods -n intelligent-sre
```

### Detection not showing issues
```bash
# Wait longer - metrics take time to populate
sleep 60

# Check Prometheus is scraping
curl http://localhost:30090/api/v1/targets
```

### Cleanup not working
```bash
# Manual cleanup
kubectl delete pods -n intelligent-sre -l app=e2e-test --force --grace-period=0
```

### Claude Desktop not working
```bash
# Restart Claude
killall Claude
open -a Claude

# Test API manually
curl http://localhost:30080/detection/health-score?namespace=intelligent-sre
```

---

## Benefits of This Test

✅ **Comprehensive** - Tests all detection engines at once  
✅ **Realistic** - Uses real pods with actual failures  
✅ **Automated** - One command, fully scripted  
✅ **Safe** - Automatic cleanup guaranteed  
✅ **Demo-Ready** - Perfect for showing stakeholders  
✅ **Educational** - See exactly how detection works  
✅ **Validated** - Confirms Claude Desktop integration  

---

## Perfect For

- 🎯 **Demos** - Show the platform to stakeholders
- ✅ **Validation** - Verify all features work
- 🧪 **Testing** - Check after code changes
- 📚 **Learning** - Understand how detection works
- 🤖 **Claude Integration** - Validate MCP tools

---

## Example Session

```bash
$ ./tests/test-e2e-with-claude.sh

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
End-to-End Test with Claude Desktop Integration
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

This test will:
  1. ✅ Verify baseline system health
  2. 🚀 Deploy test infrastructure
  3. ⏱️  Wait for issues to develop
  4. 🤖 Give you time to test with Claude Desktop
  5. 🧹 Automatically clean up

Press Enter to continue...

[... deploys pods ...]

⏱️  Time remaining: 01:30

[... shows detection results ...]

🤖 Now it's time to test with Claude Desktop!

Try these prompts:
  • "What is the health score?"
  • "Detect all anomalies"
  • [... 20+ prompts ...]

⚠️  When done, press Enter to clean up...

[... cleanup happens automatically ...]

✅ End-to-End Test Complete! 🎉
```

---

## Related Files

- **Main Script**: `tests/test-e2e-with-claude.sh`
- **Menu Access**: `tests/test-scenarios.sh` (Option 11)
- **Documentation**: This file

---

## Next Steps After Testing

1. ✅ Verify cleanup: `kubectl get pods -n intelligent-sre -l app=e2e-test`
2. ✅ Check baseline: `curl http://localhost:30080/detection/health-score`
3. ✅ Review results with your team
4. ✅ Deploy to production with confidence!
