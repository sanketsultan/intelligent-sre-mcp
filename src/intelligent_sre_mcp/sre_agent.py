"""
SRE Incident Response Agent
============================
Uses Claude claude-opus-4-6 with the intelligent-sre-mcp FastAPI backend to autonomously
investigate and (optionally) remediate production incidents.

Two-phase pattern
-----------------
  Phase 1 — Investigation (always runs first)
    1. Call `detect_comprehensive` for a full system health snapshot
    2. Run targeted PromQL queries to quantify anomalies
    3. Inspect failing pods, Kubernetes events, and container logs
    4. Correlate signals to pinpoint the root cause
    5. Summarise findings clearly

  Phase 2 — Remediation (enabled via --remediate flag)
    1. Apply the minimal effective healing action
    2. Re-query metrics to verify recovery
    3. Record the outcome in the learning store
    4. Write a concise post-mortem

Usage
-----
  # Investigate only (safe, no changes)
  python -m intelligent_sre_mcp.sre_agent "What is the current health of the system?"

  # Investigate + remediate
  python -m intelligent_sre_mcp.sre_agent --remediate "Pods are CrashLooping in production"

  # Custom API endpoint
  python -m intelligent_sre_mcp.sre_agent --api-url http://my-cluster:30080 "Check health"
"""

from __future__ import annotations

import argparse
import asyncio
import json
import logging
import os
import sys
from typing import Any

import anthropic
import httpx

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# System Prompt
# ---------------------------------------------------------------------------

SYSTEM_PROMPT = """\
You are an expert Site Reliability Engineer (SRE) operating an intelligent incident response \
system. Your mission is to maintain system health through systematic investigation and targeted \
remediation.

## Methodology

### Phase 1 — Investigation (ALWAYS run first)
1. Call `detect_comprehensive` for a full system health snapshot
2. Run targeted PromQL queries to quantify anomalies (error rates, latencies, saturation)
3. Inspect failing pods, recent Kubernetes events, and relevant container logs
4. Call `detect_correlations` to identify root cause chains
5. Summarise your findings clearly — state exactly *what* is broken and *why*

### Phase 2 — Remediation (only when approved by the user or explicitly requested)
1. Apply the minimal effective healing action
2. Re-query the relevant metrics after ~30 s to verify recovery
3. Record the outcome via `record_agent_activity`
4. Write a concise post-mortem:
   - **What happened** / **Root cause** / **Action taken** / **How to prevent**
5. Create a GitHub Issue post-mortem via `create_github_issue`

## Runbooks & Alerts
- Call `get_alerts` early — Alertmanager already knows which SLOs are breached
- Call `list_runbooks` to identify the best matching playbook for the incident type
- Call `execute_runbook` to get an ordered, tool-by-tool investigation and remediation plan
- Follow the runbook steps in order unless evidence points to a different root cause

## Safety Rules
- NEVER start remediation before completing Phase 1 investigation
- NEVER drain or cordon a node without explicit user confirmation in the prompt
- Prefer restart > scale > rollback in that order of invasiveness
- Always explain your reasoning BEFORE taking any healing action
- Set `dry_run=true` first when probing destructive operations
- If unsure about a remediation, ask the user for confirmation
"""

# ---------------------------------------------------------------------------
# Tool Definitions — Investigation
# ---------------------------------------------------------------------------

INVESTIGATION_TOOLS: list[dict[str, Any]] = [
    {
        "name": "detect_comprehensive",
        "description": (
            "Run a full system health analysis combining anomaly detection, pattern recognition, "
            "and correlation analysis. Always call this FIRST to get a system-wide snapshot "
            "before running targeted queries."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "namespace": {
                    "type": "string",
                    "description": "Kubernetes namespace to scope analysis (omit for all namespaces)",
                }
            },
        },
    },
    {
        "name": "prom_query",
        "description": (
            "Execute a PromQL instant query against Prometheus. Use to measure specific signals "
            "such as error rates, latency percentiles, or resource saturation. "
            "Examples: "
            "  rate(http_requests_total{status=~'5..'}[5m])  — HTTP 5xx rate  "
            "  histogram_quantile(0.99, rate(request_duration_seconds_bucket[5m]))  — p99 latency"
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "PromQL expression to execute",
                }
            },
            "required": ["query"],
        },
    },
    {
        "name": "get_health_score",
        "description": (
            "Get an overall system health score (0–100) with a per-category breakdown. "
            "Scores below 70 indicate degraded state; below 50 indicate critical."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "namespace": {"type": "string", "description": "Kubernetes namespace (optional)"}
            },
        },
    },
    {
        "name": "detect_anomalies",
        "description": (
            "Detect statistical anomalies across CPU, memory, pod restarts, and pending pods. "
            "Returns anomalies with severity levels (CRITICAL / WARNING / INFO)."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "namespace": {"type": "string", "description": "Kubernetes namespace (optional)"}
            },
        },
    },
    {
        "name": "get_failing_pods",
        "description": (
            "List all pods currently in a non-Running/non-Completed state "
            "(CrashLoopBackOff, OOMKilled, Pending, Error, etc.)."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "namespace": {"type": "string", "description": "Kubernetes namespace (optional)"}
            },
        },
    },
    {
        "name": "get_pods",
        "description": "List all pods and their current status in a namespace.",
        "input_schema": {
            "type": "object",
            "properties": {
                "namespace": {
                    "type": "string",
                    "description": "Kubernetes namespace (omit for all namespaces)",
                }
            },
        },
    },
    {
        "name": "get_pod_logs",
        "description": (
            "Retrieve recent log lines from a specific pod. "
            "Use after identifying a failing pod to read error messages."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "namespace": {"type": "string", "description": "Kubernetes namespace"},
                "pod_name": {"type": "string", "description": "Exact pod name"},
                "tail_lines": {
                    "type": "integer",
                    "description": "Number of recent lines to return (default: 100)",
                },
            },
            "required": ["namespace", "pod_name"],
        },
    },
    {
        "name": "get_events",
        "description": (
            "Retrieve Kubernetes events (warnings, scheduling failures, restarts). "
            "Essential for diagnosing OOMKilled, ImagePullBackOff, or node pressure issues."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "namespace": {"type": "string", "description": "Kubernetes namespace (optional)"}
            },
        },
    },
    {
        "name": "get_nodes",
        "description": (
            "Get status and resource pressure of all cluster nodes. "
            "Use when suspecting node-level issues (DiskPressure, MemoryPressure, NotReady)."
        ),
        "input_schema": {"type": "object", "properties": {}},
    },
    {
        "name": "detect_patterns",
        "description": (
            "Identify recurring failure patterns and cyclic resource spikes from historical data. "
            "Useful for distinguishing transient blips from systematic regressions."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "namespace": {"type": "string", "description": "Kubernetes namespace (optional)"}
            },
        },
    },
    {
        "name": "detect_correlations",
        "description": (
            "Correlate metrics, events, and anomalies to surface root cause chains. "
            "Call after `detect_comprehensive` to get deeper causal analysis."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "namespace": {"type": "string", "description": "Kubernetes namespace (optional)"}
            },
        },
    },
    {
        "name": "record_agent_activity",
        "description": (
            "Record a high-signal summary of your investigation in the learning store. "
            "Call at the end of Phase 1 with intent, key observations, steps taken, and findings."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "intent": {
                    "type": "string",
                    "description": "What you were asked to investigate",
                },
                "inputs_summary": {
                    "type": "string",
                    "description": "Key signals and anomalies observed",
                },
                "action_taken": {
                    "type": "string",
                    "description": "Investigation steps executed",
                },
                "outcome": {
                    "type": "string",
                    "description": "Root cause and findings summary",
                },
                "notes": {"type": "string", "description": "Any additional context"},
            },
            "required": ["intent", "inputs_summary", "action_taken"],
        },
    },
    {
        "name": "get_alerts",
        "description": (
            "Query Alertmanager for currently firing or pending alerts. "
            "Returns alert name, severity, summary annotation, and how long each alert has been "
            "active. Call this early in investigation to know which SLOs are breached and get "
            "immediate context on the blast radius. "
            "Requires ALERTMANAGER_URL env var (default: http://localhost:9093)."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "state": {
                    "type": "string",
                    "enum": ["active", "suppressed", "unprocessed"],
                    "description": "Filter by alert state — omit for all alerts",
                },
                "severity": {
                    "type": "string",
                    "description": "Filter by severity label, e.g. 'critical' or 'warning'",
                },
            },
        },
    },
    {
        "name": "list_runbooks",
        "description": (
            "List all available structured runbooks with their titles, descriptions, and symptom "
            "lists. Use to identify which runbook best matches the current incident before calling "
            "execute_runbook for the full step-by-step plan."
        ),
        "input_schema": {"type": "object", "properties": {}},
    },
    {
        "name": "execute_runbook",
        "description": (
            "Return the full structured investigation and remediation steps for a specific runbook. "
            "Each step includes the tool to call, default arguments, and the rationale. "
            "Follow the steps in order — they are designed to go from least to most invasive."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "name": {
                    "type": "string",
                    "enum": [
                        "db_connection_exhaustion",
                        "high_latency_cascade",
                        "elevated_error_rates",
                    ],
                    "description": "Runbook name returned by list_runbooks",
                }
            },
            "required": ["name"],
        },
    },
]

# ---------------------------------------------------------------------------
# Tool Definitions — Healing (Phase 2)
# ---------------------------------------------------------------------------

HEALING_TOOLS: list[dict[str, Any]] = [
    {
        "name": "restart_pod",
        "description": (
            "Restart a specific pod by deleting it; Kubernetes will recreate it automatically. "
            "Use when a pod is stuck, CrashLoopBackOff, or OOMKilled. "
            "Set dry_run=true to preview without applying."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "namespace": {"type": "string", "description": "Kubernetes namespace"},
                "pod_name": {"type": "string", "description": "Exact pod name to restart"},
                "dry_run": {
                    "type": "boolean",
                    "description": "Preview change without applying (default: false)",
                },
            },
            "required": ["namespace", "pod_name"],
        },
    },
    {
        "name": "delete_failed_pods",
        "description": (
            "Delete all Failed-phase pods in a namespace to clean up completed failures. "
            "Safe to use; does not affect Running pods."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "namespace": {
                    "type": "string",
                    "description": "Kubernetes namespace (required)",
                },
                "dry_run": {
                    "type": "boolean",
                    "description": "Preview only (default: false)",
                },
            },
            "required": ["namespace"],
        },
    },
    {
        "name": "scale_deployment",
        "description": (
            "Scale a deployment to a target number of replicas. "
            "Use to increase capacity during load spikes or reduce to 0 for emergency stop."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "namespace": {"type": "string"},
                "deployment_name": {"type": "string"},
                "replicas": {
                    "type": "integer",
                    "description": "Target replica count (0–20)",
                },
                "dry_run": {"type": "boolean", "description": "Preview only (default: false)"},
            },
            "required": ["namespace", "deployment_name", "replicas"],
        },
    },
    {
        "name": "rollback_deployment",
        "description": (
            "Roll back a deployment to its previous revision. "
            "Use ONLY after confirming the current revision introduced the regression. "
            "This is the most invasive healing action — prefer restart or scale first."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "namespace": {"type": "string"},
                "deployment_name": {"type": "string"},
                "revision": {
                    "type": "integer",
                    "description": "Target revision number (omit to use previous revision)",
                },
                "dry_run": {"type": "boolean", "description": "Preview only (default: false)"},
            },
            "required": ["namespace", "deployment_name"],
        },
    },
    {
        "name": "create_problem",
        "description": (
            "Create a problem (incident) record in the learning store. "
            "Call at the start of Phase 2 to track this incident."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "title": {
                    "type": "string",
                    "description": "Short incident title, e.g. 'CrashLoopBackOff: api-server'",
                },
                "namespace": {"type": "string", "description": "Affected namespace"},
                "severity": {
                    "type": "string",
                    "enum": ["critical", "high", "medium", "low"],
                    "description": "Incident severity",
                },
                "summary": {
                    "type": "string",
                    "description": "Initial incident summary from Phase 1 investigation",
                },
            },
            "required": ["title"],
        },
    },
    {
        "name": "update_problem",
        "description": (
            "Update a problem record's status and write a post-mortem summary. "
            "Call at the end of Phase 2 with the final resolution summary."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "problem_id": {
                    "type": "integer",
                    "description": "Problem ID returned by create_problem",
                },
                "status": {
                    "type": "string",
                    "enum": ["open", "investigating", "resolved", "closed"],
                    "description": "New status",
                },
                "summary": {
                    "type": "string",
                    "description": (
                        "Post-mortem: what happened / root cause / action taken / prevention"
                    ),
                },
            },
            "required": ["problem_id", "status"],
        },
    },
    {
        "name": "create_github_issue",
        "description": (
            "Create a GitHub Issue as a post-mortem document for this incident. "
            "Call at the end of Phase 2 after the incident is resolved. "
            "Write a complete post-mortem: what happened, root cause, timeline, action taken, "
            "and how to prevent recurrence. "
            "Requires GITHUB_TOKEN and GITHUB_REPO (format: owner/repo) env vars."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "title": {
                    "type": "string",
                    "description": (
                        "Issue title, e.g. '[Post-mortem] CrashLoopBackOff: api-server 2026-03-15'"
                    ),
                },
                "body": {
                    "type": "string",
                    "description": (
                        "Full post-mortem in Markdown. Include sections: "
                        "## What Happened, ## Root Cause, ## Timeline, "
                        "## Action Taken, ## Prevention"
                    ),
                },
                "labels": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": (
                        "GitHub labels to apply, e.g. ['incident', 'post-mortem', 'severity:high']"
                    ),
                },
            },
            "required": ["title", "body"],
        },
    },
]

# ---------------------------------------------------------------------------
# Tool Executor
# ---------------------------------------------------------------------------


async def _call_api(
    http: httpx.AsyncClient, method: str, path: str, **kwargs: Any
) -> dict | list | str:
    """Call the intelligent-sre-mcp FastAPI and return parsed JSON."""
    try:
        response = await getattr(http, method)(path, **kwargs)
        response.raise_for_status()
        return response.json()
    except httpx.HTTPStatusError as exc:
        return {
            "error": f"HTTP {exc.response.status_code}",
            "detail": exc.response.text[:500],
        }
    except httpx.TimeoutException:
        return {"error": "Request timed out. The API server may be unavailable."}
    except Exception as exc:  # noqa: BLE001
        return {"error": str(exc)}


async def execute_tool(
    http: httpx.AsyncClient,
    tool_name: str,
    tool_input: dict[str, Any],
) -> str:
    """Dispatch a tool call to the appropriate FastAPI endpoint."""
    result: Any

    match tool_name:
        # ── Investigation tools ──────────────────────────────────────────────

        case "detect_comprehensive":
            ns = tool_input.get("namespace")
            result = await _call_api(
                http,
                "get",
                "/detection/comprehensive",
                params={"namespace": ns} if ns else {},
            )

        case "prom_query":
            result = await _call_api(
                http,
                "post",
                "/query",
                json={"query": tool_input["query"]},
            )

        case "get_health_score":
            ns = tool_input.get("namespace")
            result = await _call_api(
                http,
                "get",
                "/detection/health-score",
                params={"namespace": ns} if ns else {},
            )

        case "detect_anomalies":
            ns = tool_input.get("namespace")
            result = await _call_api(
                http,
                "get",
                "/detection/anomalies",
                params={"namespace": ns} if ns else {},
            )

        case "get_failing_pods":
            ns = tool_input.get("namespace")
            result = await _call_api(
                http,
                "get",
                "/k8s/pods/failing",
                params={"namespace": ns} if ns else {},
            )

        case "get_pods":
            ns = tool_input.get("namespace")
            result = await _call_api(
                http,
                "get",
                "/k8s/pods",
                params={"namespace": ns} if ns else {},
            )

        case "get_pod_logs":
            ns = tool_input["namespace"]
            name = tool_input["pod_name"]
            params: dict[str, Any] = {}
            if "tail_lines" in tool_input:
                params["tail_lines"] = tool_input["tail_lines"]
            result = await _call_api(http, "get", f"/k8s/pods/{ns}/{name}/logs", params=params)

        case "get_events":
            ns = tool_input.get("namespace")
            result = await _call_api(
                http,
                "get",
                "/k8s/events",
                params={"namespace": ns} if ns else {},
            )

        case "get_nodes":
            result = await _call_api(http, "get", "/k8s/nodes")

        case "detect_patterns":
            ns = tool_input.get("namespace")
            result = await _call_api(
                http,
                "get",
                "/detection/patterns",
                params={"namespace": ns} if ns else {},
            )

        case "detect_correlations":
            ns = tool_input.get("namespace")
            result = await _call_api(
                http,
                "get",
                "/detection/correlations",
                params={"namespace": ns} if ns else {},
            )

        case "record_agent_activity":
            result = await _call_api(http, "post", "/learning/agent-activity", json=tool_input)

        # ── Healing tools ────────────────────────────────────────────────────

        case "restart_pod":
            result = await _call_api(
                http,
                "post",
                "/healing/restart-pod",
                params={
                    "namespace": tool_input["namespace"],
                    "pod_name": tool_input["pod_name"],
                    "dry_run": str(tool_input.get("dry_run", False)).lower(),
                },
            )

        case "delete_failed_pods":
            result = await _call_api(
                http,
                "post",
                "/healing/delete-failed-pods",
                params={
                    "namespace": tool_input["namespace"],
                    "dry_run": str(tool_input.get("dry_run", False)).lower(),
                },
            )

        case "scale_deployment":
            result = await _call_api(
                http,
                "post",
                "/healing/scale-deployment",
                params={
                    "namespace": tool_input["namespace"],
                    "deployment_name": tool_input["deployment_name"],
                    "replicas": tool_input["replicas"],
                    "dry_run": str(tool_input.get("dry_run", False)).lower(),
                },
            )

        case "rollback_deployment":
            params = {
                "namespace": tool_input["namespace"],
                "deployment_name": tool_input["deployment_name"],
                "dry_run": str(tool_input.get("dry_run", False)).lower(),
            }
            if "revision" in tool_input:
                params["revision"] = tool_input["revision"]
            result = await _call_api(http, "post", "/healing/rollback-deployment", params=params)

        case "create_problem":
            result = await _call_api(http, "post", "/learning/problems", json=tool_input)

        case "update_problem":
            problem_id = tool_input.pop("problem_id")
            result = await _call_api(
                http, "patch", f"/learning/problems/{problem_id}", json=tool_input
            )

        # ── Alertmanager ─────────────────────────────────────────────────────

        case "get_alerts":
            am_url = os.environ.get("ALERTMANAGER_URL", "http://localhost:9093")
            am_params: dict[str, Any] = {}
            filters: list[str] = []
            if state := tool_input.get("state"):
                filters.append(f'alertstate="{state}"')
            if severity := tool_input.get("severity"):
                filters.append(f'severity="{severity}"')
            if filters:
                am_params["filter"] = ",".join(filters)
            try:
                async with httpx.AsyncClient(timeout=10.0) as am_client:
                    am_resp = await am_client.get(
                        f"{am_url}/api/v2/alerts",
                        params=am_params,
                    )
                    am_resp.raise_for_status()
                    result = am_resp.json()
            except httpx.TimeoutException:
                result = {
                    "error": "Alertmanager request timed out",
                    "hint": "Is ALERTMANAGER_URL set and Alertmanager reachable?",
                }
            except Exception as exc:  # noqa: BLE001
                result = {
                    "error": str(exc),
                    "hint": "Set ALERTMANAGER_URL=http://alertmanager:9093",
                }

        # ── Runbooks ──────────────────────────────────────────────────────────

        case "list_runbooks":
            from intelligent_sre_mcp.runbooks import (
                list_runbooks as _list_runbooks,  # noqa: PLC0415
            )

            result = _list_runbooks()

        case "execute_runbook":
            from intelligent_sre_mcp.runbooks import get_runbook  # noqa: PLC0415

            rb = get_runbook(tool_input["name"])
            result = rb.to_dict() if rb else {"error": f"Runbook '{tool_input['name']}' not found"}

        # ── GitHub Issues (post-mortem) ───────────────────────────────────────

        case "create_github_issue":
            gh_token = os.environ.get("GITHUB_TOKEN", "")
            gh_repo = os.environ.get("GITHUB_REPO", "")
            if not gh_token or not gh_repo:
                result = {
                    "error": "GITHUB_TOKEN and GITHUB_REPO environment variables are required",
                    "hint": "Set GITHUB_REPO=owner/repo and GITHUB_TOKEN=ghp_...",
                }
            else:
                gh_payload: dict[str, Any] = {
                    "title": tool_input["title"],
                    "body": tool_input["body"],
                    "labels": tool_input.get("labels", ["incident", "post-mortem"]),
                }
                try:
                    async with httpx.AsyncClient(timeout=15.0) as gh_client:
                        gh_resp = await gh_client.post(
                            f"https://api.github.com/repos/{gh_repo}/issues",
                            json=gh_payload,
                            headers={
                                "Authorization": f"Bearer {gh_token}",
                                "Accept": "application/vnd.github.v3+json",
                                "X-GitHub-Api-Version": "2022-11-28",
                            },
                        )
                        gh_resp.raise_for_status()
                        gh_data = gh_resp.json()
                        result = {
                            "issue_number": gh_data["number"],
                            "url": gh_data["html_url"],
                            "title": gh_data["title"],
                            "state": gh_data["state"],
                        }
                except httpx.HTTPStatusError as exc:
                    result = {
                        "error": f"GitHub API error: HTTP {exc.response.status_code}",
                        "detail": exc.response.text[:400],
                    }
                except Exception as exc:  # noqa: BLE001
                    result = {"error": str(exc)}

        case _:
            result = {"error": f"Unknown tool: {tool_name}"}

    return json.dumps(result, default=str, indent=2)


# ---------------------------------------------------------------------------
# Agent Loop
# ---------------------------------------------------------------------------


DEFAULT_MODEL = os.getenv("SRE_MODEL", "claude-haiku-4-5")

# Cost reference (per million tokens, as of 2025):
#   claude-haiku-4-5   $0.25 input  / $1.25 output   (default — cheapest)
#   claude-sonnet-4-5  $3.00 input  / $15.00 output  (better reasoning)
#   claude-opus-4-6    $15.00 input / $75.00 output  (most capable, most expensive)
SUPPORTED_MODELS = {
    "haiku":  "claude-haiku-4-5",
    "sonnet": "claude-sonnet-4-5",
    "opus":   "claude-opus-4-6",
    # also accept full model IDs directly
    "claude-haiku-4-5":  "claude-haiku-4-5",
    "claude-sonnet-4-5": "claude-sonnet-4-5",
    "claude-opus-4-6":   "claude-opus-4-6",
}


async def run_sre_agent(
    prompt: str,
    *,
    remediate: bool = False,
    api_base: str = "http://localhost:30080",
    api_key: str | None = None,
    model: str = DEFAULT_MODEL,
    verbose: bool = False,
) -> str:
    """
    Run the SRE incident response agent.

    Args:
        prompt:    User's question or incident description.
        remediate: If True, healing tools are available alongside investigation tools.
                   If False (default), the agent runs in investigation-only mode.
        api_base:  Base URL of the intelligent-sre-mcp FastAPI server.
        api_key:   Anthropic API key (falls back to ANTHROPIC_API_KEY env var).
        model:     Claude model to use. Accepts short aliases (haiku/sonnet/opus)
                   or full model IDs. Defaults to SRE_MODEL env var or haiku.
        verbose:   If True, emit DEBUG logs.

    Returns:
        The agent's final text response.
    """
    log_level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(
        level=log_level,
        format="%(asctime)s %(levelname)-8s %(name)s: %(message)s",
    )

    tools = INVESTIGATION_TOOLS + (HEALING_TOOLS if remediate else [])
    mode = "investigate+remediate" if remediate else "investigate-only"
    resolved_model = SUPPORTED_MODELS.get(model, model)
    logger.info("SRE agent starting | mode=%s model=%s api=%s", mode, resolved_model, api_base)

    resolved_key = api_key or os.environ.get("ANTHROPIC_API_KEY")
    if not resolved_key:
        raise ValueError(
            "ANTHROPIC_API_KEY environment variable is not set. "
            "Export it or pass api_key= explicitly."
        )

    claude = anthropic.AsyncAnthropic(api_key=resolved_key)
    messages: list[dict[str, Any]] = [{"role": "user", "content": prompt}]
    final_text = ""

    async with httpx.AsyncClient(base_url=api_base, timeout=30.0) as http:
        while True:
            # Stream the response so text appears incrementally
            async with claude.messages.stream(
                model=resolved_model,
                max_tokens=4096,
                system=SYSTEM_PROMPT,
                tools=tools,
                messages=messages,
            ) as stream:
                async for text in stream.text_stream:
                    print(text, end="", flush=True)

                response = await stream.get_final_message()

            if response.stop_reason == "end_turn":
                print()  # trailing newline
                final_text = "".join(
                    block.text for block in response.content if hasattr(block, "text")
                )
                break

            if response.stop_reason != "tool_use":
                logger.warning("Unexpected stop_reason=%s; stopping.", response.stop_reason)
                break

            # ── Execute tool calls ───────────────────────────────────────────
            tool_results: list[dict[str, Any]] = []
            for block in response.content:
                if block.type != "tool_use":
                    continue

                print(
                    f"\n\033[34m[tool] {block.name}({json.dumps(block.input, separators=(',', ':'))})\033[0m",
                    flush=True,
                )
                logger.debug("Executing tool %s with input %s", block.name, block.input)

                result_text = await execute_tool(http, block.name, dict(block.input))
                tool_results.append(
                    {
                        "type": "tool_result",
                        "tool_use_id": block.id,
                        "content": result_text,
                    }
                )

            # Append assistant message (includes tool_use blocks) + tool results
            messages.append({"role": "assistant", "content": response.content})
            messages.append({"role": "user", "content": tool_results})

    logger.info("SRE agent finished | mode=%s", mode)
    return final_text


# ---------------------------------------------------------------------------
# CLI Entry Point
# ---------------------------------------------------------------------------


def main() -> None:
    parser = argparse.ArgumentParser(
        prog="sre-agent",
        description="SRE Incident Response Agent — powered by Claude",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""\
Examples:
  # Investigate current system health (safe — no changes)
  python -m intelligent_sre_mcp.sre_agent "What is the current health of the system?"

  # Investigate a specific incident
  python -m intelligent_sre_mcp.sre_agent "High 5xx error rate on the api service since 10 min"

  # Investigate AND remediate
  python -m intelligent_sre_mcp.sre_agent --remediate \\
      "Pods are CrashLoopBackOff in the intelligent-sre namespace"

  # Point to a custom cluster
  python -m intelligent_sre_mcp.sre_agent \\
      --api-url http://my-cluster-nodeport:30080 \\
      "Check health"
""",
    )
    parser.add_argument(
        "prompt",
        help="Incident description or health-check question",
    )
    parser.add_argument(
        "--remediate",
        action="store_true",
        default=False,
        help="Enable healing tools (Phase 2). Default: investigation-only.",
    )
    parser.add_argument(
        "--api-url",
        default=os.getenv("API_URL", "http://localhost:30080"),
        metavar="URL",
        help="intelligent-sre-mcp API base URL (default: %(default)s)",
    )
    parser.add_argument(
        "--model",
        default=DEFAULT_MODEL,
        metavar="MODEL",
        help=(
            "Claude model to use. Aliases: haiku (default, cheapest), sonnet, opus. "
            "Or set SRE_MODEL env var. (default: %(default)s)"
        ),
    )
    parser.add_argument(
        "--verbose",
        action="store_true",
        default=False,
        help="Enable DEBUG logging",
    )
    args = parser.parse_args()

    try:
        asyncio.run(
            run_sre_agent(
                args.prompt,
                remediate=args.remediate,
                api_base=args.api_url,
                model=args.model,
                verbose=args.verbose,
            )
        )
    except KeyboardInterrupt:
        print("\n\n[interrupted]", file=sys.stderr)
        sys.exit(130)
    except ValueError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
