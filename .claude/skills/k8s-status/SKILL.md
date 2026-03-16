---
description: Show a full health summary of the intelligent-sre Kubernetes cluster. Use when checking if the stack is healthy, all pods are running, and services are reachable.
disable-model-invocation: false
allowed-tools: Bash
---

Show a full health summary of the intelligent-sre Kubernetes cluster.

Steps:
1. Run `kubectl get pods -n intelligent-sre -o wide` -- show all pods with node assignment
2. Run `kubectl get events -n intelligent-sre --sort-by=.lastTimestamp | tail -15` -- recent events
3. Check service endpoints are responding:
   - `curl -sf http://localhost:30080/health` -- API
   - `curl -sf http://localhost:30090/-/healthy` -- Prometheus
   - `curl -sf http://localhost:30300/api/health` -- Grafana
   - `curl -sf http://localhost:30093/-/healthy` -- Alertmanager
4. Run `curl -sf http://localhost:30080/alerts | jq 'length'` to show count of stored alerts
5. Print a summary table:
   - Pod count: X running, Y not ready
   - Services: which are up/down
   - Recent events: any warnings or errors
   - Alerts in DB: count
6. If any pods are not Running, suggest running `/sre investigate failing pods in intelligent-sre namespace`
