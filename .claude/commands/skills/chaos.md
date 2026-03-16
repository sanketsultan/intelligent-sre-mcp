---
description: Deploy or teardown chaos pods for testing SRE agent remediation. Use when setting up failure scenarios or cleaning up after a chaos test.
argument-hint: deploy|teardown|status
disable-model-invocation: true
allowed-tools: Bash
---

Deploy or teardown chaos pods for testing the SRE agent remediation.

Usage: /chaos deploy    — inject broken pods into the cluster
Usage: /chaos teardown  — remove all chaos pods
Usage: /chaos status    — show current chaos pod states

Steps:
1. Parse $ARGUMENTS (deploy / teardown / status). Default to status if none given.

For `deploy`:
1. Run `kubectl apply -k k8s/chaos/`
2. Wait 10 seconds then run `kubectl get pods -n intelligent-sre -l chaos=true`
3. Show the pod states — expect: crash-worker (CrashLoopBackOff), pending-worker (Pending), sick-api (Running/NotReady)
4. Tell the user to run `/sre --remediate investigate and fix all broken pods in intelligent-sre namespace` to trigger remediation

For `teardown`:
1. Run `kubectl delete -k k8s/chaos/ --ignore-not-found`
2. Confirm pods are gone with `kubectl get pods -n intelligent-sre -l chaos=true`

For `status`:
1. Run `kubectl get pods -n intelligent-sre` and highlight any non-Running pods
2. Run `kubectl get events -n intelligent-sre --sort-by=.lastTimestamp | tail -20` for recent events
