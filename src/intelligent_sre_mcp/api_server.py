import os
import httpx
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from typing import Optional, List, Dict, Any
from datetime import datetime
import uvicorn

# OpenTelemetry imports
from opentelemetry import trace, metrics
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor
from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
from opentelemetry.sdk.metrics import MeterProvider
from opentelemetry.exporter.otlp.proto.grpc.metric_exporter import OTLPMetricExporter
from opentelemetry.sdk.metrics.export import PeriodicExportingMetricReader
from opentelemetry.sdk.resources import Resource
from opentelemetry.semconv.resource import ResourceAttributes
from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
from opentelemetry.instrumentation.httpx import HTTPXClientInstrumentor

# Import Kubernetes tools
from intelligent_sre_mcp.tools.k8s_tools import KubernetesTools
from intelligent_sre_mcp.tools.anomaly_detection import AnomalyDetector
from intelligent_sre_mcp.tools.pattern_recognition import PatternRecognizer
from intelligent_sre_mcp.tools.correlation import CorrelationEngine
from intelligent_sre_mcp.tools.healing_actions import HealingActions
from kubernetes import client

PROM_URL = os.getenv("PROMETHEUS_URL", "http://prometheus:9090").rstrip("/")
TIMEOUT = float(os.getenv("REQUEST_TIMEOUT", "10"))
OTLP_ENDPOINT = os.getenv("OTLP_ENDPOINT", "http://otel-collector:4317")
SERVICE_NAME = os.getenv("SERVICE_NAME", "intelligent-sre-mcp")
ENABLE_TRACING = os.getenv("ENABLE_TRACING", "true").lower() == "true"

app = FastAPI(title="Intelligent SRE MCP API", version="0.1.0")

# Initialize Kubernetes tools
k8s_tools = KubernetesTools()

# Initialize Phase 2: Intelligent Detection tools
anomaly_detector = AnomalyDetector(PROM_URL)
pattern_recognizer = PatternRecognizer(PROM_URL)
correlation_engine = CorrelationEngine(PROM_URL)

# Initialize Phase 3: Self-Healing Actions
healing_actions = HealingActions(
    core_api=client.CoreV1Api(),
    apps_api=client.AppsV1Api()
)

# OTel configuration
def configure_otel():
    if not ENABLE_TRACING:
        print(f"OpenTelemetry tracing disabled (ENABLE_TRACING={ENABLE_TRACING})")
        return
    
    try:
        resource = Resource.create({
            ResourceAttributes.SERVICE_NAME: SERVICE_NAME,
            ResourceAttributes.SERVICE_VERSION: "0.1.0",
        })
        
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
        
        print(f"OpenTelemetry configured: {OTLP_ENDPOINT}")
    except Exception as e:
        print(f" Failed to configure OpenTelemetry: {e}")
        print("   Continuing without tracing...")

configure_otel()

class QueryRequest(BaseModel):
    query: str

class QueryResponse(BaseModel):
    status: str
    data: dict

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
    return {
        "service": "Intelligent SRE MCP API",
        "version": "0.1.0",
        "prometheus_url": PROM_URL
    }

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
    previous: bool = False
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
    resource_name: Optional[str] = None
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
def detect_metric_spike(
    query: str,
    duration: str = "1h",
    spike_multiplier: float = 2.0
):
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
                "labels": a.labels or {}
            }
            for a in anomalies
        ]
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
        "overall_status": health["status"]
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
def rollback_deployment(namespace: str, deployment_name: str, revision: Optional[int] = None, dry_run: bool = False):
    """
    Rollback a deployment to a previous revision
    Query params: namespace, deployment_name, revision (optional, default: previous), dry_run (optional, default: false)
    """
    result = healing_actions.rollback_deployment(namespace, deployment_name, revision, dry_run)
    return result

@app.post("/healing/cordon-node")
def cordon_node(node_name: str, dry_run: bool = False):
    """
    Cordon a node (mark as unschedulable)
    Query params: node_name, dry_run (optional, default: false)
    """
    result = healing_actions.cordon_node(node_name, dry_run)
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

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8080)
