"""
SRE Runbooks
============
Structured investigation + remediation playbooks for common production incidents.

Each runbook has two phases:
  - investigate: ordered diagnostic steps to confirm the root cause
  - remediate:   ordered actions from least-invasive to most-invasive

Usage (from sre_agent.py tool dispatcher):
  result = execute_runbook("db_connection_exhaustion")
  result = execute_runbook("high_latency_cascade")
  result = execute_runbook("elevated_error_rates")
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class RunbookStep:
    """One step inside a runbook phase."""

    order: int
    action: str  # human-readable description of the step
    tool: str | None  # SRE agent tool to call (None = manual/observation step)
    tool_args: dict  # default args for the tool call (agent may override)
    rationale: str  # why this step is important


@dataclass
class Runbook:
    name: str
    title: str
    description: str
    symptoms: list[str]
    investigate: list[RunbookStep]
    remediate: list[RunbookStep]
    prevention: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "title": self.title,
            "description": self.description,
            "symptoms": self.symptoms,
            "investigate": [
                {
                    "order": s.order,
                    "action": s.action,
                    "tool": s.tool,
                    "tool_args": s.tool_args,
                    "rationale": s.rationale,
                }
                for s in self.investigate
            ],
            "remediate": [
                {
                    "order": s.order,
                    "action": s.action,
                    "tool": s.tool,
                    "tool_args": s.tool_args,
                    "rationale": s.rationale,
                }
                for s in self.remediate
            ],
            "prevention": self.prevention,
        }


# ---------------------------------------------------------------------------
# Runbook: Database Connection Pool Exhaustion
# ---------------------------------------------------------------------------

DB_CONNECTION_EXHAUSTION = Runbook(
    name="db_connection_exhaustion",
    title="Database Connection Pool Exhaustion",
    description=(
        "The application cannot acquire DB connections because the pool is exhausted. "
        "Typically caused by a misconfigured pool size, a connection leak, or a sudden "
        "traffic spike that overwhelms the available connections."
    ),
    symptoms=[
        "HTTP 500 errors on endpoints that touch the database",
        "P99 latency spike (requests queue waiting for a connection)",
        "Logs show 'connection pool exhausted' or 'could not obtain connection'",
        "DB connection count metric near or at pool size limit",
    ],
    investigate=[
        RunbookStep(
            order=1,
            action="Get overall system health snapshot",
            tool="detect_comprehensive",
            tool_args={},
            rationale="Establish baseline — confirm the issue is DB-related and not broader",
        ),
        RunbookStep(
            order=2,
            action="Query HTTP 5xx error rate over last 5 minutes",
            tool="prom_query",
            tool_args={"query": "rate(http_requests_total{status=~'5..'}[5m])"},
            rationale="Quantify the blast radius — how many requests are failing?",
        ),
        RunbookStep(
            order=3,
            action="Query active DB connections vs pool size",
            tool="prom_query",
            tool_args={"query": "db_connections_active / db_pool_size"},
            rationale="Confirm pool saturation — ratio near 1.0 means exhaustion",
        ),
        RunbookStep(
            order=4,
            action="Query P99 request latency",
            tool="prom_query",
            tool_args={
                "query": "histogram_quantile(0.99, rate(request_duration_seconds_bucket[5m]))"
            },
            rationale="Latency spike confirms requests are queueing for connections",
        ),
        RunbookStep(
            order=5,
            action="Check for failing pods in the application namespace",
            tool="get_failing_pods",
            tool_args={"namespace": "intelligent-sre"},
            rationale="Identify which pods are affected — may be a subset",
        ),
        RunbookStep(
            order=6,
            action="Read application pod logs for connection error messages",
            tool="get_pod_logs",
            tool_args={"namespace": "intelligent-sre", "tail_lines": 200},
            rationale="Confirm 'pool exhausted' messages and find the first occurrence timestamp",
        ),
        RunbookStep(
            order=7,
            action="Check Kubernetes events for recent restarts or OOM events",
            tool="get_events",
            tool_args={"namespace": "intelligent-sre"},
            rationale="Rule out memory pressure causing connection drops",
        ),
    ],
    remediate=[
        RunbookStep(
            order=1,
            action="Restart the most-affected pod to release leaked connections (dry run first)",
            tool="restart_pod",
            tool_args={"dry_run": True},
            rationale="Immediate relief — frees all connections held by that pod process",
        ),
        RunbookStep(
            order=2,
            action="Verify error rate drops after restart",
            tool="prom_query",
            tool_args={"query": "rate(http_requests_total{status=~'5..'}[2m])"},
            rationale="Confirm the restart had the desired effect before proceeding",
        ),
        RunbookStep(
            order=3,
            action="If multiple pods affected, scale down then up to cycle all connections",
            tool="scale_deployment",
            tool_args={"replicas": 1, "dry_run": True},
            rationale="Rolling restart ensures all leaked connections are released",
        ),
        RunbookStep(
            order=4,
            action="Create incident record",
            tool="create_problem",
            tool_args={
                "title": "DB Connection Pool Exhaustion",
                "severity": "high",
                "summary": "Pool exhaustion causing 5xx errors — runbook: db_connection_exhaustion",
            },
            rationale="Track the incident for post-mortem and pattern analysis",
        ),
    ],
    prevention=[
        "Set DB_POOL_SIZE to at least 2× the peak concurrent request rate",
        "Add Prometheus alert: db_connections_active/db_pool_size > 0.8 for 5m",
        "Enable connection timeout + retry with exponential backoff in the application",
        "Use pgBouncer as a connection pooler in front of PostgreSQL for large fleets",
    ],
)

# ---------------------------------------------------------------------------
# Runbook: High Latency Cascade
# ---------------------------------------------------------------------------

HIGH_LATENCY_CASCADE = Runbook(
    name="high_latency_cascade",
    title="High Latency Cascade",
    description=(
        "P99 latency has spiked across one or more services, often caused by a slow "
        "downstream dependency (DB, external API, or a saturated node) that backs up "
        "the entire request queue."
    ),
    symptoms=[
        "P99 latency > SLO threshold (e.g., > 500ms)",
        "Increasing queue depth or thread pool saturation",
        "Timeout errors appearing in logs",
        "CPU/memory not saturated (rules out resource exhaustion as primary cause)",
    ],
    investigate=[
        RunbookStep(
            order=1,
            action="Get overall system health and active anomalies",
            tool="detect_comprehensive",
            tool_args={},
            rationale="Get a complete picture before drilling down",
        ),
        RunbookStep(
            order=2,
            action="Query P50, P95, P99 latency to identify affected percentile range",
            tool="prom_query",
            tool_args={
                "query": (
                    "histogram_quantile(0.99, rate(request_duration_seconds_bucket[5m])) or "
                    "histogram_quantile(0.95, rate(request_duration_seconds_bucket[5m]))"
                )
            },
            rationale="High P99 but normal P50 = tail latency issue. High P50 = systemic slowdown",
        ),
        RunbookStep(
            order=3,
            action="Check DB connection wait time",
            tool="prom_query",
            tool_args={"query": "db_connection_wait_seconds_p99"},
            rationale="DB wait is the most common root cause of latency cascades",
        ),
        RunbookStep(
            order=4,
            action="Check node CPU and memory pressure",
            tool="get_nodes",
            tool_args={},
            rationale="Node saturation causes all pods on that node to slow down",
        ),
        RunbookStep(
            order=5,
            action="Detect correlation between latency spike and other signals",
            tool="detect_correlations",
            tool_args={},
            rationale="Find what changed at the same time the latency spiked",
        ),
        RunbookStep(
            order=6,
            action="Check recent deployments for timing correlation",
            tool="get_events",
            tool_args={},
            rationale="A recent deploy may have introduced a slow code path",
        ),
        RunbookStep(
            order=7,
            action="Read application logs for timeout messages",
            tool="get_pod_logs",
            tool_args={"tail_lines": 300},
            rationale="Timeout stack traces identify the slow dependency",
        ),
    ],
    remediate=[
        RunbookStep(
            order=1,
            action="If caused by a bad deploy — rollback the deployment (dry run first)",
            tool="rollback_deployment",
            tool_args={"dry_run": True},
            rationale="Fastest recovery if a code change introduced the slowdown",
        ),
        RunbookStep(
            order=2,
            action="If caused by resource pressure — scale up the deployment",
            tool="scale_deployment",
            tool_args={"dry_run": True},
            rationale="More replicas distribute load and reduce per-instance queue depth",
        ),
        RunbookStep(
            order=3,
            action="Verify latency returns to normal after action",
            tool="prom_query",
            tool_args={
                "query": "histogram_quantile(0.99, rate(request_duration_seconds_bucket[2m]))"
            },
            rationale="Confirm the fix is working before closing the incident",
        ),
    ],
    prevention=[
        "Set per-request timeouts on all outbound calls (DB, HTTP, gRPC)",
        "Add circuit breakers to prevent cascading failures from slow dependencies",
        "Add SLO burn-rate alerts for latency in addition to error rate",
        "Profile slow endpoints under load before each release",
    ],
)

# ---------------------------------------------------------------------------
# Runbook: Elevated Error Rates
# ---------------------------------------------------------------------------

ELEVATED_ERROR_RATES = Runbook(
    name="elevated_error_rates",
    title="Elevated HTTP Error Rates",
    description=(
        "5xx error rate has exceeded the SLO threshold. Could be caused by "
        "application bugs, dependency failures, resource exhaustion, or a bad deploy."
    ),
    symptoms=[
        "HTTP 500/502/503/504 rate above SLO (e.g., > 0.5% of requests)",
        "Alerts firing in Alertmanager",
        "Error budget burn rate accelerating",
        "User-facing errors or timeout messages",
    ],
    investigate=[
        RunbookStep(
            order=1,
            action="Get full system health snapshot",
            tool="detect_comprehensive",
            tool_args={},
            rationale="Understand the full scope before investigating a specific cause",
        ),
        RunbookStep(
            order=2,
            action="Query error rate broken down by status code",
            tool="prom_query",
            tool_args={"query": "rate(http_requests_total{status=~'5..'}[5m]) by (status)"},
            rationale=(
                "500 = app bug, 502 = upstream unavailable, "
                "503 = overloaded, 504 = timeout. Status code narrows the cause."
            ),
        ),
        RunbookStep(
            order=3,
            action="Check currently firing alerts",
            tool="get_alerts",
            tool_args={},
            rationale="Alertmanager may already have context on what is firing and for how long",
        ),
        RunbookStep(
            order=4,
            action="Check for failing pods",
            tool="get_failing_pods",
            tool_args={},
            rationale="CrashLoopBackOff or OOMKilled pods cause 502/503 errors at the LB",
        ),
        RunbookStep(
            order=5,
            action="Read error logs from the failing service",
            tool="get_pod_logs",
            tool_args={"tail_lines": 300},
            rationale="Stack traces identify the exact exception and code path causing 5xx",
        ),
        RunbookStep(
            order=6,
            action="Detect patterns — is this a recurring issue?",
            tool="detect_patterns",
            tool_args={},
            rationale="If this has happened before, the learning store may have the fix",
        ),
        RunbookStep(
            order=7,
            action="Correlate error spike with recent deployments or config changes",
            tool="detect_correlations",
            tool_args={},
            rationale="Timing correlation between deploy and error rate spike is strong evidence",
        ),
    ],
    remediate=[
        RunbookStep(
            order=1,
            action="Restart crashing pods immediately (dry run first)",
            tool="restart_pod",
            tool_args={"dry_run": True},
            rationale="Fastest recovery for CrashLoopBackOff — may be transient failure",
        ),
        RunbookStep(
            order=2,
            action="If caused by a bad deploy — rollback",
            tool="rollback_deployment",
            tool_args={"dry_run": True},
            rationale="If error rate started with a deploy, rollback restores previous state",
        ),
        RunbookStep(
            order=3,
            action="Delete stale Failed pods to clean up the namespace",
            tool="delete_failed_pods",
            tool_args={"dry_run": True},
            rationale="Removes noise and frees resource quota for new healthy pods",
        ),
        RunbookStep(
            order=4,
            action="Verify error rate drops back below SLO threshold",
            tool="prom_query",
            tool_args={"query": "rate(http_requests_total{status=~'5..'}[2m])"},
            rationale="Confirm recovery before creating post-mortem",
        ),
        RunbookStep(
            order=5,
            action="Create GitHub issue post-mortem",
            tool="create_github_issue",
            tool_args={"labels": ["incident", "post-mortem"]},
            rationale="Document the incident for future reference and pattern learning",
        ),
    ],
    prevention=[
        "Enable SLO burn-rate alerts (2% budget in 1h = page, 5% in 6h = ticket)",
        "Run canary deploys — route 5% of traffic to new version before full rollout",
        "Add readiness probe that checks DB connectivity before accepting traffic",
        "Set up automated rollback trigger when error rate exceeds 1% for 5m post-deploy",
    ],
)

# ---------------------------------------------------------------------------
# Registry
# ---------------------------------------------------------------------------

RUNBOOKS: dict[str, Runbook] = {
    rb.name: rb for rb in [DB_CONNECTION_EXHAUSTION, HIGH_LATENCY_CASCADE, ELEVATED_ERROR_RATES]
}


def get_runbook(name: str) -> Runbook | None:
    """Return a runbook by name, or None if not found."""
    return RUNBOOKS.get(name)


def list_runbooks() -> list[dict]:
    """Return a summary of all available runbooks."""
    return [
        {
            "name": rb.name,
            "title": rb.title,
            "description": rb.description,
            "symptoms": rb.symptoms,
        }
        for rb in RUNBOOKS.values()
    ]
