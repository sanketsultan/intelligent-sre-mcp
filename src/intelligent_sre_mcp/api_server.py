import os
import httpx
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from typing import Optional, List, Dict, Any
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

PROM_URL = os.getenv("PROMETHEUS_URL", "http://prometheus:9090").rstrip("/")
TIMEOUT = float(os.getenv("REQUEST_TIMEOUT", "10"))
OTLP_ENDPOINT = os.getenv("OTLP_ENDPOINT", "http://otel-collector:4317")
SERVICE_NAME = os.getenv("SERVICE_NAME", "intelligent-sre-mcp")
ENABLE_TRACING = os.getenv("ENABLE_TRACING", "true").lower() == "true"

app = FastAPI(title="Intelligent SRE MCP API", version="0.1.0")

# Initialize Kubernetes tools
k8s_tools = KubernetesTools()

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

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8080)


# if __name__ == "__main__":
#     uvicorn.run(app, host="0.0.0.0", port=8080)
