---
description: Run the full end-to-end chaos and remediation test to verify the SRE agent can detect and fix all simulated failure modes.
disable-model-invocation: true
allowed-tools: Bash
---

Run the full end-to-end chaos + remediation test to verify the SRE agent can detect and fix all failure modes.

Steps:
1. Check ANTHROPIC_API_KEY is set — fail fast if missing
2. Check the stack is running: `kubectl get pods -n intelligent-sre` — all pods should be Running
3. Run `./scripts/test-remediation.sh` and capture output
4. The script will:
   - Deploy chaos pods (crash-worker, pending-worker, sick-api, dependent-worker)
   - Wait for Alertmanager to fire alerts
   - Trigger the SRE agent remediation pass
   - Verify all pods recover to Running/Ready
   - Clean up chaos pods
5. Report PASS or FAIL with a summary of which pods were fixed and which (if any) remained broken
6. If the test fails, show the relevant kubectl logs and suggest next steps
