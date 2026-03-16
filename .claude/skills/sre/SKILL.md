---
description: Run the SRE agent against the live stack. Use when investigating incidents, checking system health, or remediating broken pods and services.
argument-hint: [--remediate] <prompt>
disable-model-invocation: true
allowed-tools: Bash
---

Run the SRE agent against the live stack with the given prompt.

Usage: /sre <prompt>
Usage: /sre --remediate <prompt>

Steps:
1. Check that ANTHROPIC_API_KEY is set in .env (source .env if needed)
2. Check that the API is reachable: `curl -sf http://localhost:30080/health` (K8s) or `http://localhost:8080/health` (Docker Compose)
3. If --remediate is in $ARGUMENTS, run:
   `python -m intelligent_sre_agent.sre_agent --remediate --model sonnet "$ARGUMENTS"`
   Otherwise run:
   `python -m intelligent_sre_agent.sre_agent "$ARGUMENTS"`
4. Print the agent output including the [tokens] cost line at the end
5. If the API is not reachable, tell the user to run `make dev` or `./scripts/setup.sh` first
