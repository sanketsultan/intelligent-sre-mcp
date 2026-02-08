import os
import httpx
from mcp.server.fastmcp import FastMCP

# OpenTelemetry imports
from opentelemetry import trace, metrics
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor
from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
from opentelemetry.sdk.metrics import MeterProvider
from opentelemetry.exporter.otlp.proto.grpc.metric_exporter import OTLPMetricExporter
from opentelemetry.sdk.metrics.export import PeriodicExportingMetricReader

PROM_URL = os.getenv("PROMETHEUS_URL", "http://localhost:9090").rstrip("/")
TIMEOUT = float(os.getenv("REQUEST_TIMEOUT", "10"))

mcp = FastMCP("intelligent-sre-mcp")

# OTel configuration
def configure_otel():
    # Tracing setup
    trace.set_tracer_provider(TracerProvider())
    tracer_provider = trace.get_tracer_provider()
    otlp_trace_exporter = OTLPSpanExporter(endpoint="localhost:4317", insecure=True)
    span_processor = BatchSpanProcessor(otlp_trace_exporter)
    tracer_provider.add_span_processor(span_processor)

    # Metrics setup
    metric_exporter = OTLPMetricExporter(endpoint="localhost:4317", insecure=True)
    metric_reader = PeriodicExportingMetricReader(metric_exporter)
    meter_provider = MeterProvider(metric_readers=[metric_reader])
    metrics.set_meter_provider(meter_provider)

configure_otel()


def prom_query_instant(query: str) -> dict:
    url = f"{PROM_URL}/api/v1/query"
    with httpx.Client(timeout=TIMEOUT) as client:
        r = client.get(url, params={"query": query})
        r.raise_for_status()
        return r.json()


@mcp.tool()
def prom_query(query: str) -> str:
    """
    Run a PromQL instant query against Prometheus and return the JSON response.
    Example query: up
    """
    data = prom_query_instant(query)
    return str(data)


def main():
    # IMPORTANT: do not print to stdout in stdio servers
    mcp.run(transport="stdio")


if __name__ == "__main__":
    main()
