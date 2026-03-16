---
description: Generate a postmortem report for a resolved incident. Use after an incident has been fixed to document what happened, why, and how to prevent it.
argument-hint: <incident description or alert ID>
disable-model-invocation: true
allowed-tools: Bash, Read
---

Generate a structured postmortem report for a resolved incident.

Usage: /postmortem <incident description>
Usage: /postmortem <alert ID from DB>

Steps:
1. If $ARGUMENTS looks like an alert ID (numeric), fetch the alert details:
   `curl -sf http://localhost:30080/alerts/$ARGUMENTS | jq .`
   Otherwise use $ARGUMENTS as the incident description.

2. Gather context:
   - Run `curl -sf http://localhost:30080/alerts | jq '.[-10:]'` to see recent alerts
   - Run `kubectl get events -n intelligent-sre --sort-by=.lastTimestamp | tail -30`
   - Run `kubectl logs -n intelligent-sre -l app=intelligent-sre-agent --tail=100`

3. Write a postmortem with these sections:

   ## Incident Summary
   - Date and time
   - Duration (detected to resolved)
   - Severity (critical / warning)
   - Services affected

   ## Timeline
   - When the issue started (from logs/events)
   - When it was detected (alert fired or proactive check)
   - What the agent did (investigation steps, tools called)
   - When it was resolved

   ## Root Cause
   - What was broken and why (be specific: which config, which pod, which env var)

   ## Impact
   - Which pods/services were affected
   - Any error rate or latency impact visible in Prometheus

   ## What Went Well
   - Did the agent detect it automatically?
   - Did remediation succeed without human intervention?
   - Was the audit trail complete?

   ## What Could Be Improved
   - Was detection slow? Should the proactive check threshold be lower?
   - Did the agent need multiple attempts?
   - Is there a runbook gap?

   ## Action Items
   | Item | Owner | Priority |
   |------|-------|----------|
   | Add runbook for this failure mode | SRE | high |
   | Add alert rule if missing | SRE | medium |
   | Update chaos test to cover this case | Dev | medium |

4. Save the report to `postmortems/YYYY-MM-DD-<short-title>.md`
5. Print the file path and a short summary
