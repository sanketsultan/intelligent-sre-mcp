import json
import logging
import os
import time
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

import httpx
import uvicorn
from fastapi import BackgroundTasks, FastAPI, HTTPException

try:
    from kubernetes import client as k8s_client
    _K8S_AVAILABLE = True
except ImportError:
    k8s_client = None  # type: ignore[assignment]
    _K8S_AVAILABLE = False

# OpenTelemetry imports
from opentelemetry import metrics, trace
from opentelemetry.exporter.otlp.proto.grpc.metric_exporter import OTLPMetricExporter
from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
from opentelemetry.instrumentation.httpx import HTTPXClientInstrumentor
from opentelemetry.sdk.metrics import MeterProvider
from opentelemetry.sdk.metrics.export import PeriodicExportingMetricReader
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor
from opentelemetry.semconv.resource import ResourceAttributes
from pydantic import BaseModel

from intelligent_sre_agent.alert_store import AlertStore
from intelligent_sre_agent.remediation_engine import RemediationEngine, list_playbooks
from intelligent_sre_agent.remediation_store import RemediationStore
from intelligent_sre_agent.tools.action_learning import ActionHistoryStore, set_current_problem_id
from intelligent_sre_agent.tools.anomaly_detection import AnomalyDetector
from intelligent_sre_agent.tools.correlation import CorrelationEngine
from intelligent_sre_agent.tools.healing_actions import HealingActions

# Import Kubernetes tools
from intelligent_sre_agent.tools.k8s_tools import KubernetesTools
from intelligent_sre_agent.tools.pattern_recognition import PatternRecognizer

# ---------------------------------------------------------------------------
# Structured JSON logging
# ---------------------------------------------------------------------------


class _JsonFormatter(logging.Formatter):
    """Emit one JSON object per log record – compatible with Loki/Promtail."""

    def format(self, record: logging.LogRecord) -> str:  # noqa: A003
        payload: dict = {
            "ts": datetime.fromtimestamp(record.created, tz=timezone.utc).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "msg": record.getMessage(),
        }
        if record.exc_info:
            payload["exc"] = self.formatException(record.exc_info)
        # Merge any extra fields passed via the `extra=` kwarg
        for key, value in record.__dict__.items():
            if key not in logging.LogRecord.__dict__ and not key.startswith("_"):
                payload[key] = value
        return json.dumps(payload, default=str)


def _configure_logging() -> logging.Logger:
    handler = logging.StreamHandler()
    handler.setFormatter(_JsonFormatter())
    root = logging.getLogger()
    root.handlers.clear()
    root.addHandler(handler)
    root.setLevel(logging.INFO)
    return logging.getLogger("intelligent_sre_agent")


logger = _configure_logging()

# ---------------------------------------------------------------------------

PROM_URL = os.getenv("PROMETHEUS_URL", "http://prometheus:9090").rstrip("/")
TIMEOUT = float(os.getenv("REQUEST_TIMEOUT", "10"))
OTLP_ENDPOINT = os.getenv("OTLP_ENDPOINT", "http://otel-collector:4317")
SERVICE_NAME = os.getenv("SERVICE_NAME", "intelligent-sre-agent")
ENABLE_TRACING = os.getenv("ENABLE_TRACING", "true").lower() == "true"
# When the agent runs inside the K8s pod it must reach the API server on its
# internal port (8080), not the external NodePort (30080) which is not bound to
# localhost inside the container.  Override via env var in the deployment manifest.
API_URL = os.getenv("API_URL", "http://localhost:8080")
# Model used by the webhook-triggered remediation pass.  Sonnet is the minimum
# recommended capability level for multi-step tool-based remediation.  Haiku is
# too weak to reliably chain detect -> scale_deployment calls.
SRE_REMEDIATION_MODEL = os.getenv("SRE_REMEDIATION_MODEL", "claude-sonnet-4-5")
# Model used for the investigation-only pass (cheap, fast).
SRE_INVESTIGATION_MODEL = os.getenv("SRE_MODEL", "claude-haiku-4-5")
# Model used when sonnet remediation produces "STILL BROKEN" — escalate to a
# more capable model before paging a human.
SRE_ESCALATION_MODEL = os.getenv("SRE_ESCALATION_MODEL", "claude-opus-4-6")
# max_tokens ceiling for the Phase 2 remediation call.  This is an OUTPUT cap —
# you only pay for tokens actually generated, not the limit.  4096 is sufficient
# for all normal remediation responses.  Raise via env var if the agent is being
# truncated mid-response (check remediation_summary ends with "...").
SRE_MAX_TOKENS = int(os.getenv("SRE_MAX_TOKENS", "4096"))
# Minimum alert severity that triggers auto-remediation (Phase 2).
# "critical" = only critical alerts (default, conservative)
# "warning"  = warning + critical alerts
# "info"     = all alerts (use with caution)
SRE_AUTO_REMEDIATE_SEVERITY = os.getenv("SRE_AUTO_REMEDIATE_SEVERITY", "critical").lower()
# Health score (0-100) below which the proactive CronJob triggers auto-remediation.
SRE_PROACTIVE_HEALTH_THRESHOLD = int(os.getenv("SRE_PROACTIVE_HEALTH_THRESHOLD", "50"))

# Severity ordering: alerts at or above the configured threshold trigger Phase 2.
_SEVERITY_ORDER: dict[str, int] = {"info": 0, "warning": 1, "critical": 2}


def _should_remediate(severity: str) -> bool:
    """Return True if alert severity meets the configured remediation threshold."""
    alert_level = _SEVERITY_ORDER.get(severity.lower(), 0)
    threshold_level = _SEVERITY_ORDER.get(SRE_AUTO_REMEDIATE_SEVERITY, 2)
    return alert_level >= threshold_level
# Max characters of Phase 1 investigation to embed in the Phase 2 sonnet prompt.
# Sonnet charges per INPUT token too; a 10 000-char investigation summary adds
# ~2 500 input tokens (~$0.008) on every remediation call.  Truncating to 3 000
# chars captures all root-cause detail the agent needs without the noise.
_INVESTIGATION_CTX_LIMIT = int(os.getenv("SRE_INVESTIGATION_CTX_CHARS", "3000"))
SLACK_BOT_TOKEN = os.getenv("SLACK_BOT_TOKEN", "")
SLACK_CHANNEL = os.getenv("SLACK_CHANNEL", "")
# GitHub incident tickets — created automatically when the agent cannot auto-remediate.
# Set GITHUB_REPO to "owner/repo" (e.g. "acme/infra-incidents") and GITHUB_TOKEN to a
# Personal Access Token or GitHub App token with Issues write permission.
GITHUB_TOKEN = os.getenv("GITHUB_TOKEN", "")
GITHUB_REPO = os.getenv("GITHUB_REPO", "")

app = FastAPI(title="Intelligent SRE Agent API", version="0.1.0")

# Initialize Kubernetes tools
k8s_tools = KubernetesTools()

# Initialize Phase 2: Intelligent Detection tools
anomaly_detector = AnomalyDetector(PROM_URL)
pattern_recognizer = PatternRecognizer(PROM_URL)
correlation_engine = CorrelationEngine(PROM_URL)

# Initialize Phase 3: Self-Healing Actions
action_store = ActionHistoryStore()
alert_store = AlertStore()
remediation_store = RemediationStore()

healing_actions = HealingActions(
    core_api=k8s_client.CoreV1Api() if _K8S_AVAILABLE and k8s_tools.available else None,
    apps_api=k8s_client.AppsV1Api() if _K8S_AVAILABLE and k8s_tools.available else None,
    policy_api=k8s_client.PolicyV1Api() if _K8S_AVAILABLE and k8s_tools.available else None,
    action_store=action_store,
)

# Initialize the auto-remediation engine (notify_callback wired in at module level)
remediation_engine = RemediationEngine(
    k8s_tools=k8s_tools,
    healing_actions=healing_actions,
    store=remediation_store,
)


@app.middleware("http")
async def log_tool_invocation(request, call_next):
    start_time = time.perf_counter()
    body_bytes = await request.body()
    response = await call_next(request)
    duration_ms = (time.perf_counter() - start_time) * 1000
    try:
        body_text = body_bytes.decode("utf-8") if body_bytes else None
    except UnicodeDecodeError:
        body_text = None
    query_params = str(request.query_params) if request.query_params else None
    header_problem_id = request.headers.get("X-Problem-Id")
    try:
        header_problem_id = int(header_problem_id) if header_problem_id else None
    except ValueError:
        header_problem_id = None
    request_problem_id = header_problem_id
    if request_problem_id is None and request.url.path not in {"/health", "/"}:
        fingerprint = f"{request.method}:{request.url.path}?{query_params or ''}"
        title = f"{request.method} {request.url.path}"
        request_problem_id = action_store.get_or_create_problem(
            title=title,
            fingerprint=fingerprint,
        )
    set_current_problem_id(request_problem_id)
    try:
        action_store.record_tool_invocation(
            method=request.method,
            path=request.url.path,
            query_params=query_params,
            body=body_text,
            status_code=response.status_code,
            duration_ms=duration_ms,
            problem_id=request_problem_id,
        )
    except Exception:
        pass
    finally:
        set_current_problem_id(None)

    logger.info(
        "%s %s %s",
        request.method,
        request.url.path,
        response.status_code,
        extra={
            "http_method": request.method,
            "http_path": request.url.path,
            "http_status": response.status_code,
            "duration_ms": round(duration_ms, 2),
            "problem_id": request_problem_id,
        },
    )
    return response


# OTel configuration
def configure_otel():
    if not ENABLE_TRACING:
        logger.info("OpenTelemetry tracing disabled", extra={"enable_tracing": ENABLE_TRACING})
        return

    try:
        resource = Resource.create(
            {
                ResourceAttributes.SERVICE_NAME: SERVICE_NAME,
                ResourceAttributes.SERVICE_VERSION: "0.1.0",
            }
        )

        # Tracing setup
        trace.set_tracer_provider(TracerProvider(resource=resource))
        tracer_provider = trace.get_tracer_provider()
        otlp_trace_exporter = OTLPSpanExporter(endpoint=OTLP_ENDPOINT, insecure=True)
        span_processor = BatchSpanProcessor(otlp_trace_exporter)
        tracer_provider.add_span_processor(span_processor)

        # Metrics setup
        metric_exporter = OTLPMetricExporter(endpoint=OTLP_ENDPOINT, insecure=True)
        metric_reader = PeriodicExportingMetricReader(metric_exporter)
        meter_provider = MeterProvider(resource=resource, metric_readers=[metric_reader])
        metrics.set_meter_provider(meter_provider)

        # Auto-instrument FastAPI and httpx
        FastAPIInstrumentor.instrument_app(app)
        HTTPXClientInstrumentor().instrument()

        logger.info("OpenTelemetry configured", extra={"otlp_endpoint": OTLP_ENDPOINT})
    except Exception as e:
        logger.warning(
            "Failed to configure OpenTelemetry; continuing without tracing", extra={"error": str(e)}
        )


configure_otel()


class QueryRequest(BaseModel):
    query: str


class QueryResponse(BaseModel):
    status: str
    data: dict


class AgentActivityRequest(BaseModel):
    intent: str
    inputs_summary: str
    action_taken: str
    outcome: Optional[str] = None
    notes: Optional[str] = None
    timestamp: Optional[str] = None
    problem_id: Optional[int] = None


class ProblemCreateRequest(BaseModel):
    title: str
    namespace: Optional[str] = None
    resource: Optional[str] = None
    severity: Optional[str] = None
    status: str = "open"
    summary: Optional[str] = None


class ProblemUpdateRequest(BaseModel):
    status: str
    summary: Optional[str] = None


class ActionOutcomeRequest(BaseModel):
    action_id: int
    outcome: str
    resolution_time_seconds: Optional[float] = None
    notes: Optional[str] = None


# ---------------------------------------------------------------------------
# Alertmanager webhook payload models
# ---------------------------------------------------------------------------


class AlertmanagerAlert(BaseModel):
    """Single alert inside an Alertmanager webhook POST body."""

    status: str  # firing | resolved
    labels: Dict[str, Any] = {}
    annotations: Dict[str, Any] = {}
    startsAt: Optional[str] = None
    endsAt: Optional[str] = None
    generatorURL: Optional[str] = None
    fingerprint: Optional[str] = None


class AlertmanagerWebhook(BaseModel):
    """Alertmanager v4 webhook payload."""

    version: Optional[str] = None
    groupKey: Optional[str] = None
    status: Optional[str] = None
    receiver: Optional[str] = None
    groupLabels: Dict[str, Any] = {}
    commonLabels: Dict[str, Any] = {}
    commonAnnotations: Dict[str, Any] = {}
    externalURL: Optional[str] = None
    alerts: List[AlertmanagerAlert] = []


def prom_query_instant(query: str) -> dict:
    url = f"{PROM_URL}/api/v1/query"
    with httpx.Client(timeout=TIMEOUT) as client:
        r = client.get(url, params={"query": query})
        r.raise_for_status()
        return r.json()


@app.get("/health")
def health_check():
    """Health check endpoint"""
    return {"status": "healthy", "prometheus_url": PROM_URL}


@app.get("/")
def root():
    """Root endpoint"""
    return {"service": "Intelligent SRE MCP API", "version": "0.1.0", "prometheus_url": PROM_URL}


@app.post("/query", response_model=QueryResponse)
def query_prometheus(request: QueryRequest):
    """
    Query Prometheus using PromQL
    Example: {"query": "up"}
    """
    try:
        result = prom_query_instant(request.query)
        return QueryResponse(status="success", data=result)
    except httpx.HTTPError as e:
        raise HTTPException(status_code=500, detail=f"Prometheus query failed: {str(e)}")


@app.get("/targets")
def get_targets():
    """Get all Prometheus targets"""
    try:
        result = prom_query_instant("up")
        return result
    except httpx.HTTPError as e:
        raise HTTPException(status_code=500, detail=f"Failed to get targets: {str(e)}")


# ============================================================
# Kubernetes Diagnostic Endpoints
# ============================================================


@app.get("/k8s/pods")
def get_k8s_pods(namespace: Optional[str] = None):
    """
    Get all pods with their status.
    Query params: namespace (optional)
    """
    return k8s_tools.get_all_pods(namespace)


@app.get("/k8s/pods/failing")
def get_failing_k8s_pods(namespace: Optional[str] = None):
    """
    Get pods that are in failing states.
    Query params: namespace (optional)
    """
    return k8s_tools.get_failing_pods(namespace)


@app.get("/k8s/pods/{namespace}/{pod_name}/logs")
def get_k8s_pod_logs(
    namespace: str,
    pod_name: str,
    container: Optional[str] = None,
    tail_lines: int = 100,
    previous: bool = False,
):
    """
    Get logs from a specific pod/container.
    Path params: namespace, pod_name
    Query params: container, tail_lines, previous
    """
    return k8s_tools.get_pod_logs(namespace, pod_name, container, tail_lines, previous)


@app.get("/k8s/pods/{namespace}/{pod_name}")
def describe_k8s_pod(namespace: str, pod_name: str):
    """
    Get detailed information about a pod (similar to kubectl describe).
    Path params: namespace, pod_name
    """
    return k8s_tools.describe_pod(namespace, pod_name)


@app.get("/k8s/nodes")
def get_k8s_nodes():
    """Get status of all nodes in the cluster."""
    return k8s_tools.get_node_status()


@app.get("/k8s/deployments/{namespace}/{deployment_name}")
def get_k8s_deployment(namespace: str, deployment_name: str):
    """
    Get status of a specific deployment.
    Path params: namespace, deployment_name
    """
    return k8s_tools.get_deployment_status(namespace, deployment_name)


@app.get("/k8s/events")
def get_k8s_events(
    namespace: Optional[str] = None,
    resource_type: Optional[str] = None,
    resource_name: Optional[str] = None,
):
    """
    Get Kubernetes events.
    Query params: namespace, resource_type, resource_name (all optional)
    """
    return k8s_tools.get_events(namespace, resource_type, resource_name)


# ============================================================
# Phase 2: Intelligent Detection Endpoints
# ============================================================


@app.get("/detection/anomalies")
def detect_anomalies(namespace: Optional[str] = None):
    """
    Detect anomalies in CPU, memory, pod restarts, and pending pods.
    Query params: namespace (optional)
    """
    return anomaly_detector.detect_all_anomalies(namespace)


@app.get("/detection/health-score")
def get_health_score(namespace: Optional[str] = None):
    """
    Calculate overall health score (0-100) based on detected anomalies.
    Query params: namespace (optional)
    """
    return anomaly_detector.get_health_score(namespace)


@app.get("/detection/patterns")
def detect_patterns(namespace: Optional[str] = None):
    """
    Detect patterns such as recurring failures, cyclic spikes, resource exhaustion.
    Query params: namespace (optional)
    """
    return pattern_recognizer.analyze_all_patterns(namespace)


@app.get("/detection/correlations")
def detect_correlations(namespace: Optional[str] = None):
    """
    Correlate metrics, events, and anomalies to identify root causes.
    Query params: namespace (optional)
    """
    return correlation_engine.analyze_all_correlations(namespace)


@app.get("/detection/spike")
def detect_metric_spike(query: str, duration: str = "1h", spike_multiplier: float = 2.0):
    """
    Detect sudden spikes in any metric.
    Query params: query (PromQL), duration, spike_multiplier
    """
    anomalies = anomaly_detector.detect_metric_spikes(query, duration, spike_multiplier)
    return {
        "status": "success",
        "anomalies": [
            {
                "metric": a.metric_name,
                "current_value": a.current_value,
                "expected_range": a.expected_range,
                "deviation": a.deviation,
                "level": a.level.value,
                "timestamp": a.timestamp,
                "description": a.description,
                "labels": a.labels or {},
            }
            for a in anomalies
        ],
    }


@app.get("/detection/comprehensive")
def comprehensive_analysis(namespace: Optional[str] = None):
    """
    Run comprehensive analysis: anomalies + patterns + correlations.
    Query params: namespace (optional)
    """
    health = anomaly_detector.get_health_score(namespace)
    anomalies = anomaly_detector.detect_all_anomalies(namespace)
    patterns = pattern_recognizer.analyze_all_patterns(namespace)
    correlations = correlation_engine.analyze_all_correlations(namespace)

    return {
        "timestamp": datetime.now().isoformat(),
        "namespace": namespace or "all",
        "health_score": health,
        "anomalies": anomalies,
        "patterns": patterns,
        "correlations": correlations,
        "overall_status": health["status"],
    }


# ==================== Phase 3: Self-Healing Actions ====================


@app.post("/healing/restart-pod")
def restart_pod(namespace: str, pod_name: str, dry_run: bool = False):
    """
    Restart a pod by deleting it (controller will recreate)
    Query params: namespace, pod_name, dry_run (optional, default: false)
    """
    result = healing_actions.restart_pod(namespace, pod_name, dry_run)
    return result


@app.post("/healing/delete-failed-pods")
def delete_failed_pods(namespace: str, label_selector: Optional[str] = None, dry_run: bool = False):
    """
    Delete all failed/completed pods in a namespace
    Query params: namespace, label_selector (optional), dry_run (optional, default: false)
    """
    result = healing_actions.delete_failed_pods(namespace, label_selector, dry_run)
    return result


@app.post("/healing/scale-deployment")
def scale_deployment(namespace: str, deployment_name: str, replicas: int, dry_run: bool = False):
    """
    Scale a deployment to specified number of replicas
    Query params: namespace, deployment_name, replicas, dry_run (optional, default: false)
    """
    result = healing_actions.scale_deployment(namespace, deployment_name, replicas, dry_run)
    return result


@app.post("/healing/rollback-deployment")
def rollback_deployment(
    namespace: str, deployment_name: str, revision: Optional[int] = None, dry_run: bool = False
):
    """
    Rollback a deployment to a previous revision
    Query params: namespace, deployment_name, revision (optional, default: previous), dry_run (optional, default: false)
    """
    result = healing_actions.rollback_deployment(namespace, deployment_name, revision, dry_run)
    return result


class PatchDeploymentRequest(BaseModel):
    namespace: str
    deployment_name: str
    patch: Dict[str, Any]
    dry_run: bool = False


@app.post("/healing/patch-deployment")
def patch_deployment_endpoint(req: PatchDeploymentRequest):
    """Apply a strategic merge patch to fix a deployment's configuration.

    Use to repair the root cause instead of emergency-stopping the pod:
      - Remove an impossible nodeSelector keeping pods Pending
      - Fix/remove a readiness probe pointing at the wrong port
      - Update a container command or env var that causes CrashLoopBackOff
      - Fix resource requests that violate a LimitRange

    Body JSON: {"namespace": "...", "deployment_name": "...", "patch": {...}, "dry_run": false}
    """
    result = healing_actions.patch_deployment(
        req.namespace, req.deployment_name, req.patch, req.dry_run
    )
    return result


@app.post("/healing/cordon-node")
def cordon_node(node_name: str, dry_run: bool = False):
    """
    Cordon a node (mark as unschedulable)
    Query params: node_name, dry_run (optional, default: false)
    """
    result = healing_actions.cordon_node(node_name, dry_run)
    return result


@app.post("/healing/evict-pod")
def evict_pod_from_node(
    namespace: str, pod_name: str, dry_run: bool = False, grace_period_seconds: int = 30
):
    """
    Evict a pod from its node using the eviction API
    Query params: namespace, pod_name, dry_run (optional), grace_period_seconds (optional)
    """
    result = healing_actions.evict_pod_from_node(namespace, pod_name, dry_run, grace_period_seconds)
    return result


@app.post("/healing/drain-node")
def drain_node(
    node_name: str,
    dry_run: bool = False,
    grace_period_seconds: int = 30,
    ignore_daemonsets: bool = True,
    include_kube_system: bool = False,
):
    """
    Drain a node by evicting all non-daemonset pods
    Query params: node_name, dry_run (optional), grace_period_seconds (optional),
    ignore_daemonsets (optional), include_kube_system (optional)
    """
    result = healing_actions.drain_node(
        node_name, dry_run, grace_period_seconds, ignore_daemonsets, include_kube_system
    )
    return result


@app.post("/healing/uncordon-node")
def uncordon_node(node_name: str, dry_run: bool = False):
    """
    Uncordon a node (mark as schedulable)
    Query params: node_name, dry_run (optional, default: false)
    """
    result = healing_actions.uncordon_node(node_name, dry_run)
    return result


@app.get("/healing/action-history")
def get_action_history(hours: int = 24):
    """
    Get healing action history
    Query params: hours (optional, default: 24)
    """
    result = healing_actions.get_action_history(hours)
    return result


@app.post("/learning/agent-activity")
def record_agent_activity(request: AgentActivityRequest):
    activity_id = action_store.record_agent_activity(
        intent=request.intent,
        inputs_summary=request.inputs_summary,
        action_taken=request.action_taken,
        outcome=request.outcome,
        notes=request.notes,
        timestamp=request.timestamp,
        problem_id=request.problem_id,
    )
    return {"status": "success", "activity_id": activity_id}


@app.get("/learning/agent-activity")
def get_agent_activity(hours: int = 24, limit: int = 50):
    return action_store.list_agent_activity(hours=hours, limit=limit)


@app.post("/learning/problems")
def create_problem(request: ProblemCreateRequest):
    problem_id = action_store.create_problem(
        title=request.title,
        namespace=request.namespace,
        resource=request.resource,
        severity=request.severity,
        status=request.status,
        summary=request.summary,
    )
    return {"status": "success", "problem_id": problem_id}


@app.patch("/learning/problems/{problem_id}")
def update_problem(problem_id: int, request: ProblemUpdateRequest):
    updated = action_store.update_problem_status(
        problem_id=problem_id,
        status=request.status,
        summary=request.summary,
    )
    return {"status": "success" if updated else "not_found", "updated": updated}


@app.get("/learning/problems")
def list_problems(hours: int = 24, limit: int = 50):
    return action_store.list_problems(hours=hours, limit=limit)


@app.get("/learning/tool-invocations")
def list_tool_invocations(hours: int = 24, limit: int = 100):
    return action_store.list_tool_invocations(hours=hours, limit=limit)


@app.get("/learning/action-stats")
def get_action_stats(hours: int = 24):
    """
    Get healing action effectiveness statistics
    Query params: hours (optional, default: 24)
    """
    return healing_actions.get_action_stats(hours)


@app.get("/learning/recurring-issues")
def get_recurring_issues(hours: int = 24, min_count: int = 2):
    """
    Identify recurring issues based on healing actions
    Query params: hours (optional, default: 24), min_count (optional, default: 2)
    """
    return healing_actions.get_recurring_issues(hours, min_count)


@app.post("/learning/record-outcome")
def record_action_outcome(request: ActionOutcomeRequest):
    """
    Record the outcome and resolution time of a healing action
    """
    return healing_actions.record_action_outcome(
        action_id=request.action_id,
        outcome=request.outcome,
        resolution_time_seconds=request.resolution_time_seconds,
        notes=request.notes,
    )


# ============================================================
# Alertmanager Webhook + Alert History
# ============================================================


async def _post_slack_notification(text: str) -> None:
    """Send a plain-text message to Slack via the Web API (best-effort)."""
    if not SLACK_BOT_TOKEN or not SLACK_CHANNEL:
        return
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            await client.post(
                "https://slack.com/api/chat.postMessage",
                headers={"Authorization": f"Bearer {SLACK_BOT_TOKEN}"},
                json={"channel": SLACK_CHANNEL, "text": text},
            )
    except Exception as exc:  # noqa: BLE001
        logger.warning("Slack notification failed", extra={"error": str(exc)})


async def _create_github_incident_issue(
    alert_name: str,
    severity: str,
    investigation: str,
    remediation_log: str,
    alert_id: int | None = None,
) -> str | None:
    """Open a GitHub Issue for an unresolved incident (best-effort).

    Called automatically when the agent exhausts all remediation attempts
    (Phase 2 exception, Phase 3 STILL BROKEN, Phase 3 exception).
    Returns the issue URL on success, None if GitHub is not configured or the
    call fails.
    """
    if not GITHUB_TOKEN or not GITHUB_REPO:
        logger.debug("GitHub incident ticket skipped — GITHUB_TOKEN/GITHUB_REPO not set")
        return None

    from datetime import date  # noqa: PLC0415

    date_str = date.today().isoformat()
    title = f"[INCIDENT] {alert_name} — {date_str} (unresolved)"
    alert_ref = f"Alert ID: {alert_id}" if alert_id else "Alert ID: unknown"
    body = (
        f"## Incident Summary\n\n"
        f"- **Alert**: `{alert_name}`\n"
        f"- **Severity**: `{severity}`\n"
        f"- **Date**: {date_str}\n"
        f"- **{alert_ref}**\n"
        f"- **Status**: Could not be auto-remediated — manual intervention required\n\n"
        f"---\n\n"
        f"## Phase 1 — Investigation\n\n"
        f"```\n{investigation[:3000]}\n```\n\n"
        f"---\n\n"
        f"## Phase 2 / Phase 3 — Remediation Attempts\n\n"
        f"```\n{remediation_log[:3000]}\n```\n\n"
        f"---\n\n"
        f"## Action Required\n\n"
        f"The SRE agent tried all available remediation strategies and could not resolve this "
        f"incident. Please investigate manually and close this issue once resolved.\n"
    )
    labels = ["incident", "sre-auto-escalation", f"severity:{severity}"]
    payload: dict[str, Any] = {"title": title, "body": body, "labels": labels}
    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            resp = await client.post(
                f"https://api.github.com/repos/{GITHUB_REPO}/issues",
                json=payload,
                headers={
                    "Authorization": f"Bearer {GITHUB_TOKEN}",
                    "Accept": "application/vnd.github.v3+json",
                    "X-GitHub-Api-Version": "2022-11-28",
                },
            )
            resp.raise_for_status()
            data = resp.json()
            url: str = data["html_url"]
            logger.info(
                "GitHub incident issue created",
                extra={"alert_id": alert_id, "issue_url": url},
            )
            return url
    except Exception as exc:  # noqa: BLE001
        logger.warning(
            "Failed to create GitHub incident issue",
            extra={"alert_id": alert_id, "error": str(exc)},
        )
        return None


async def _investigate_alert(
    alert_id: int, prompt: str, alert_name: str, severity: str
) -> None:
    """Background task: run the SRE agent for a firing alert and persist results.

    Phase 1 (always) — investigation + root-cause analysis + pod-log review.
    Phase 2 (if severity >= SRE_AUTO_REMEDIATE_SEVERITY) — automated remediation.
    Phase 3 (if Phase 2 leaves anything STILL BROKEN) — escalate to opus + Slack page.

    Phase 2 receives the Phase 1 investigation results as context so it can skip
    re-investigation and proceed directly to healing actions.
    """
    # Lazy import avoids circular dependency at module load time
    from intelligent_sre_agent.sre_agent import run_sre_agent  # noqa: PLC0415

    investigation: str = ""
    try:
        investigation = await run_sre_agent(
            prompt,
            remediate=False,
            api_base=API_URL,
            model=SRE_INVESTIGATION_MODEL,
        )
        alert_store.update_investigation(
            alert_id, investigation or "No investigation output returned."
        )
        logger.info(
            "Alert investigation complete",
            extra={"alert_id": alert_id, "severity": severity},
        )
    except Exception as exc:  # noqa: BLE001
        logger.error(
            "Alert investigation failed",
            extra={"alert_id": alert_id, "error": str(exc)},
        )
        alert_store.update_investigation(
            alert_id,
            f"Investigation failed: {exc}",
        )
        # Do not attempt remediation if investigation itself failed
        return

    if not _should_remediate(severity):
        logger.info(
            "Skipping remediation — severity below threshold",
            extra={"severity": severity, "threshold": SRE_AUTO_REMEDIATE_SEVERITY},
        )
        return

    # Phase 2: remediation — pass Phase 1 findings as context so the agent
    # skips redundant re-investigation and goes straight to healing actions.
    # Truncate investigation to _INVESTIGATION_CTX_LIMIT chars to keep
    # sonnet input tokens (and cost) low.
    investigation_ctx = investigation[:_INVESTIGATION_CTX_LIMIT]
    if len(investigation) > _INVESTIGATION_CTX_LIMIT:
        investigation_ctx += "\n[... truncated for cost efficiency ...]"
    remediation_prompt = (
        f"{prompt}\n\n"
        f"PHASE 1 FINDINGS (do not re-investigate):\n{investigation_ctx}\n\n"
        f"Phase 2: patch every broken deployment now. "
        f"Call patch_deployment for each one in sequence — each has its own cooldown. "
        f"Do NOT scale to zero. Do NOT ask for confirmation. "
        f"After patching call get_deployment_status to confirm. "
        f"Output: one line per deployment: '<name>: FIXED' or '<name>: FAILED — <reason>'. "
        f"No other text."
    )
    remediation: str = ""
    try:
        remediation = await run_sre_agent(
            remediation_prompt,
            remediate=True,
            api_base=API_URL,
            model=SRE_REMEDIATION_MODEL,
            max_tokens=SRE_MAX_TOKENS,
        )
        alert_store.update_remediation(alert_id, remediation or "No remediation output returned.")
        logger.info("Alert remediation complete", extra={"alert_id": alert_id})
    except Exception as exc:  # noqa: BLE001
        logger.error(
            "Alert remediation failed",
            extra={"alert_id": alert_id, "error": str(exc)},
        )
        alert_store.update_remediation(alert_id, f"Remediation failed: {exc}")
        issue_url = await _create_github_incident_issue(
            alert_name, severity, investigation, f"Remediation failed: {exc}", alert_id
        )
        issue_ref = f"\nIncident ticket: {issue_url}" if issue_url else ""
        await _post_slack_notification(
            f"[URGENT] Remediation failed for `{alert_name}`. Error: {exc}\nManual intervention required.{issue_ref}"
        )
        return

    # Phase 3: if sonnet left anything broken, escalate to opus then page human.
    if "STILL BROKEN" not in remediation:
        return

    logger.warning(
        "Remediation incomplete — escalating to %s", SRE_ESCALATION_MODEL,
        extra={"alert_id": alert_id},
    )
    escalation_prompt = (
        f"{remediation_prompt}\n\n"
        f"PREVIOUS ATTEMPT ({SRE_REMEDIATION_MODEL}) result:\n{remediation[:800]}\n\n"
        f"Some deployments are still broken. Try alternative approaches: "
        f"if patch_deployment failed use rollback_deployment; "
        f"if rollback unavailable use restart_pod. "
        f"Fix every remaining broken deployment."
    )
    try:
        escalation = await run_sre_agent(
            escalation_prompt,
            remediate=True,
            api_base=API_URL,
            model=SRE_ESCALATION_MODEL,
            max_tokens=SRE_MAX_TOKENS,
        )
        combined = f"{remediation}\n\n[ESCALATION — {SRE_ESCALATION_MODEL}]\n{escalation}"
        alert_store.update_remediation(alert_id, combined)
        logger.info("Escalation remediation complete", extra={"alert_id": alert_id})

        if "STILL BROKEN" in (escalation or ""):
            issue_url = await _create_github_incident_issue(
                alert_name, severity, investigation, combined, alert_id
            )
            issue_ref = f"\nIncident ticket: {issue_url}" if issue_url else ""
            await _post_slack_notification(
                f"[URGENT] `{alert_name}` could not be auto-remediated after escalation to "
                f"{SRE_ESCALATION_MODEL}. Manual intervention required.\n"
                f"Latest attempt:\n{escalation[:400]}{issue_ref}"
            )
    except Exception as exc:  # noqa: BLE001
        logger.error("Escalation failed", extra={"alert_id": alert_id, "error": str(exc)})
        remediation_log = f"{remediation}\n\nEscalation failed: {exc}"
        issue_url = await _create_github_incident_issue(
            alert_name, severity, investigation, remediation_log, alert_id
        )
        issue_ref = f"\nIncident ticket: {issue_url}" if issue_url else ""
        await _post_slack_notification(
            f"[URGENT] Escalation to {SRE_ESCALATION_MODEL} failed for `{alert_name}`. "
            f"Error: {exc}\nManual intervention required.{issue_ref}"
        )


async def _run_proactive_remediation(prompt: str, health_score: int) -> None:
    """Background task triggered by the proactive health check."""
    from intelligent_sre_agent.sre_agent import run_sre_agent  # noqa: PLC0415

    try:
        result = await run_sre_agent(
            prompt,
            remediate=True,
            api_base=API_URL,
            model=SRE_REMEDIATION_MODEL,
            max_tokens=SRE_MAX_TOKENS,
        )
        logger.info(
            "Proactive remediation complete",
            extra={"health_score": health_score, "result_preview": result[:200]},
        )
        await _post_slack_notification(
            f"[PROACTIVE] Health score was {health_score}/100 — auto-remediation ran.\n{result[:500]}"
        )
    except Exception as exc:  # noqa: BLE001
        logger.error("Proactive remediation failed", extra={"error": str(exc)})


@app.post("/health/proactive-check")
async def proactive_health_check(background_tasks: BackgroundTasks) -> Dict[str, Any]:
    """Proactive health check endpoint — called by the K8s CronJob every 5 minutes.

    Fetches the current system health score and triggers investigation + remediation
    if the score drops below SRE_PROACTIVE_HEALTH_THRESHOLD (default: 50).
    Returns immediately; the agent run happens in the background.
    """
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.get(f"{API_URL}/detection/health-score")
            data = resp.json()
    except Exception as exc:  # noqa: BLE001
        logger.warning("Proactive check: health-score fetch failed", extra={"error": str(exc)})
        return {"status": "error", "error": str(exc), "action": "none"}

    health_score = data.get("score", 100)

    if health_score >= SRE_PROACTIVE_HEALTH_THRESHOLD:
        logger.debug("Proactive check: system healthy", extra={"health_score": health_score})
        return {"status": "healthy", "health_score": health_score, "action": "none"}

    prompt = (
        f"Proactive health check triggered: system health score is {health_score}/100 "
        f"(threshold: {SRE_PROACTIVE_HEALTH_THRESHOLD}). "
        f"Investigate all anomalies and remediate any broken workloads."
    )
    background_tasks.add_task(_run_proactive_remediation, prompt, health_score)
    logger.info("Proactive check triggered remediation", extra={"health_score": health_score})
    return {
        "status": "degraded",
        "health_score": health_score,
        "threshold": SRE_PROACTIVE_HEALTH_THRESHOLD,
        "action": "remediation_scheduled",
    }


@app.post("/alertmanager/webhook", status_code=202)
async def alertmanager_webhook(
    payload: AlertmanagerWebhook,
    background_tasks: BackgroundTasks,
) -> Dict[str, Any]:
    """Receive Alertmanager webhook POSTs.

    For every *firing* alert:
    1. Persist the alert to the database.
    2. Create (or reuse) a problem record.
    3. Post an optional Slack notification.
    4. Schedule a background SRE agent investigation.

    Returns 202 Accepted immediately so Alertmanager does not time out.
    """
    saved_ids: List[int] = []

    for alert in payload.alerts:
        if alert.status != "firing":
            continue  # ignore resolved alerts (no investigation needed)

        alert_name = alert.labels.get("alertname", "UnknownAlert")
        severity = alert.labels.get("severity", "")
        namespace = alert.labels.get("namespace", "")
        summary = alert.annotations.get("summary", alert_name)

        # Upsert a problem record so the alert is linked to the learning store
        fingerprint = alert.fingerprint or f"{alert_name}:{namespace}:{severity}"
        problem_id = action_store.get_or_create_problem(
            title=alert_name,
            fingerprint=fingerprint,
            namespace=namespace or None,
            severity=severity or None,
            summary=summary or None,
        )

        alert_id = alert_store.save_alert(
            alert_name=alert_name,
            status=alert.status,
            labels=alert.labels,
            annotations=alert.annotations,
            starts_at=alert.startsAt,
            ends_at=alert.endsAt,
            problem_id=problem_id,
        )
        saved_ids.append(alert_id)

        # Build a natural-language prompt for the SRE agent
        description = alert.annotations.get("description", "")
        agent_prompt = (
            f"ALERT FIRED: {alert_name}\n"
            f"Severity: {severity or 'unknown'}\n"
            f"Namespace: {namespace or 'unknown'}\n"
            f"Summary: {summary}\n"
        )
        if description:
            agent_prompt += f"Description: {description}\n"

        # Notify Slack (best-effort, does not block the response)
        slack_text = (
            f"[ALERT] *{alert_name}* | severity: {severity or 'unknown'} | "
            f"namespace: {namespace or 'unknown'}\n{summary}"
        )
        background_tasks.add_task(_post_slack_notification, slack_text)

        # Schedule the SRE agent investigation (+ conditional remediation + escalation)
        background_tasks.add_task(
            _investigate_alert, alert_id, agent_prompt, alert_name, severity
        )

        logger.info(
            "Alert received and queued for investigation",
            extra={
                "alert_name": alert_name,
                "severity": severity,
                "alert_id": alert_id,
                "problem_id": problem_id,
            },
        )

    return {
        "status": "accepted",
        "firing_alerts_received": len(saved_ids),
        "alert_ids": saved_ids,
    }


@app.get("/alerts")
def list_alerts(limit: int = 50, status: Optional[str] = None) -> List[Dict[str, Any]]:
    """List persisted alerts (most recent first).

    Query params:
      limit  — max rows (default 50)
      status — filter by status: firing | resolved (optional)
    """
    return alert_store.list_alerts(limit=limit, status=status)


@app.get("/alerts/{alert_id}")
def get_alert(alert_id: int) -> Dict[str, Any]:
    """Retrieve a single alert with its investigation and remediation summaries."""
    alert = alert_store.get_alert(alert_id)
    if alert is None:
        raise HTTPException(status_code=404, detail=f"Alert {alert_id} not found")
    return alert


# ============================================================
# Auto-Remediation Playbook Endpoints
# ============================================================


class RemediationRunRequest(BaseModel):
    """Request body for POST /remediation/run."""

    namespace: Optional[str] = None
    dry_run: bool = False


@app.post("/remediation/run")
def run_remediation(request: RemediationRunRequest) -> Dict[str, Any]:
    """Trigger an auto-remediation cycle.

    Scans the cluster (or a single namespace) for failing pods and unhealthy
    nodes, matches each issue to a pre-approved playbook, scores confidence,
    and executes fixes when confidence >= 80%.  Issues below the threshold are
    flagged for human review.

    Body (optional JSON):
      namespace — limit scan to one namespace (default: all namespaces)
      dry_run   — report what *would* happen without changing anything
    """
    # Wire the Slack notify callback so deferred issues post to #sre-alerts
    import asyncio  # noqa: PLC0415

    def _notify_sync(text: str) -> None:
        try:
            loop = asyncio.get_event_loop()
            if loop.is_running():
                asyncio.ensure_future(_post_slack_notification(text))
            else:
                loop.run_until_complete(_post_slack_notification(text))
        except Exception:  # noqa: BLE001
            pass

    remediation_engine._notify = _notify_sync  # type: ignore[assignment]

    report = remediation_engine.run(
        namespace=request.namespace,
        dry_run=request.dry_run,
    )
    return report.to_dict()


@app.get("/remediation/history")
def get_remediation_history(
    limit: int = 50,
    outcome: Optional[str] = None,
    issue_type: Optional[str] = None,
) -> List[Dict[str, Any]]:
    """List past auto-remediation runs, most recent first.

    Query params:
      limit       — max rows (default 50)
      outcome     — filter by outcome: executed | deferred_to_human | dry_run | failed
      issue_type  — filter by issue type: CrashLoopBackOff | OOMKilled | ...
    """
    return remediation_store.list_runs(limit=limit, outcome=outcome, issue_type=issue_type)


@app.get("/remediation/playbooks")
def get_remediation_playbooks() -> List[Dict[str, Any]]:
    """List all pre-approved remediation playbooks with their confidence thresholds."""
    return list_playbooks()


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8080)
