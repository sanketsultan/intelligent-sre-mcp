import os
import httpx
from mcp.server.fastmcp import FastMCP

# API endpoint (Kubernetes NodePort)
API_URL = os.getenv("API_URL", "http://localhost:30080").rstrip("/")
TIMEOUT = float(os.getenv("REQUEST_TIMEOUT", "10"))

mcp = FastMCP("intelligent-sre-mcp-client")

@mcp.tool()
def prom_query(query: str) -> str:
    """
    Run a PromQL instant query against Prometheus via the Kubernetes API and return the JSON response.
    Example query: up
    """
    try:
        with httpx.Client(timeout=TIMEOUT) as client:
            response = client.post(
                f"{API_URL}/query",
                json={"query": query},
                headers={"Content-Type": "application/json"}
            )
            response.raise_for_status()
            return str(response.json())
    except httpx.HTTPError as e:
        return f"Error querying API: {str(e)}"

@mcp.tool()
def get_targets() -> str:
    """
    Get all Prometheus targets and their status.
    """
    try:
        with httpx.Client(timeout=TIMEOUT) as client:
            response = client.get(f"{API_URL}/targets")
            response.raise_for_status()
            return str(response.json())
    except httpx.HTTPError as e:
        return f"Error getting targets: {str(e)}"

@mcp.tool()
def health_check() -> str:
    """
    Check the health of the monitoring API.
    """
    try:
        with httpx.Client(timeout=TIMEOUT) as client:
            response = client.get(f"{API_URL}/health")
            response.raise_for_status()
            return str(response.json())
    except httpx.HTTPError as e:
        return f"Error checking health: {str(e)}"

# ============================================================
# Kubernetes Diagnostic Tools
# ============================================================

@mcp.tool()
def k8s_get_all_pods(namespace: str = None) -> str:
    """
    Get all Kubernetes pods with their status.
    Args:
        namespace: Optional namespace to filter pods (None = all namespaces)
    Returns: List of pods with status, restarts, age, and readiness
    """
    try:
        with httpx.Client(timeout=TIMEOUT) as client:
            params = {"namespace": namespace} if namespace else {}
            response = client.get(f"{API_URL}/k8s/pods", params=params)
            response.raise_for_status()
            return str(response.json())
    except httpx.HTTPError as e:
        return f"Error getting pods: {str(e)}"

@mcp.tool()
def k8s_get_failing_pods(namespace: str = None) -> str:
    """
    Get Kubernetes pods that are in failing states (CrashLoopBackOff, Error, high restarts, etc.).
    Args:
        namespace: Optional namespace to filter pods (None = all namespaces)
    Returns: List of failing pods with details about their issues
    """
    try:
        with httpx.Client(timeout=TIMEOUT) as client:
            params = {"namespace": namespace} if namespace else {}
            response = client.get(f"{API_URL}/k8s/pods/failing", params=params)
            response.raise_for_status()
            return str(response.json())
    except httpx.HTTPError as e:
        return f"Error getting failing pods: {str(e)}"

@mcp.tool()
def k8s_get_pod_logs(namespace: str, pod_name: str, container: str = None, tail_lines: int = 100, previous: bool = False) -> str:
    """
    Get logs from a specific Kubernetes pod/container.
    Args:
        namespace: Pod namespace
        pod_name: Pod name
        container: Container name (optional, uses first container if not specified)
        tail_lines: Number of recent log lines to retrieve (default: 100)
        previous: Get logs from previous instance (useful for crashed containers)
    Returns: Container logs
    """
    try:
        with httpx.Client(timeout=TIMEOUT) as client:
            params = {
                "container": container,
                "tail_lines": tail_lines,
                "previous": previous
            }
            # Remove None values
            params = {k: v for k, v in params.items() if v is not None}
            
            response = client.get(f"{API_URL}/k8s/pods/{namespace}/{pod_name}/logs", params=params)
            response.raise_for_status()
            return str(response.json())
    except httpx.HTTPError as e:
        return f"Error getting pod logs: {str(e)}"

@mcp.tool()
def k8s_describe_pod(namespace: str, pod_name: str) -> str:
    """
    Get detailed information about a Kubernetes pod (similar to kubectl describe pod).
    Includes container statuses, conditions, events, and resource information.
    Args:
        namespace: Pod namespace
        pod_name: Pod name
    Returns: Detailed pod information including events and container states
    """
    try:
        with httpx.Client(timeout=TIMEOUT) as client:
            response = client.get(f"{API_URL}/k8s/pods/{namespace}/{pod_name}")
            response.raise_for_status()
            return str(response.json())
    except httpx.HTTPError as e:
        return f"Error describing pod: {str(e)}"

@mcp.tool()
def k8s_get_nodes() -> str:
    """
    Get status of all Kubernetes nodes in the cluster.
    Returns: Node information including ready status, conditions, capacity, and resource allocation
    """
    try:
        with httpx.Client(timeout=TIMEOUT) as client:
            response = client.get(f"{API_URL}/k8s/nodes")
            response.raise_for_status()
            return str(response.json())
    except httpx.HTTPError as e:
        return f"Error getting nodes: {str(e)}"

@mcp.tool()
def k8s_get_deployment(namespace: str, deployment_name: str) -> str:
    """
    Get status of a specific Kubernetes deployment.
    Args:
        namespace: Deployment namespace
        deployment_name: Deployment name
    Returns: Deployment status including replica counts, conditions, and rollout status
    """
    try:
        with httpx.Client(timeout=TIMEOUT) as client:
            response = client.get(f"{API_URL}/k8s/deployments/{namespace}/{deployment_name}")
            response.raise_for_status()
            return str(response.json())
    except httpx.HTTPError as e:
        return f"Error getting deployment: {str(e)}"

@mcp.tool()
def k8s_get_events(namespace: str = None, resource_type: str = None, resource_name: str = None) -> str:
    """
    Get recent Kubernetes events (last 50).
    Useful for understanding recent cluster activity and troubleshooting issues.
    Args:
        namespace: Optional namespace filter
        resource_type: Optional resource type filter (Pod, Node, Deployment, etc.)
        resource_name: Optional resource name filter
    Returns: List of Kubernetes events with timestamps, reasons, and messages
    """
    try:
        with httpx.Client(timeout=TIMEOUT) as client:
            params = {}
            if namespace:
                params["namespace"] = namespace
            if resource_type:
                params["resource_type"] = resource_type
            if resource_name:
                params["resource_name"] = resource_name
            
            response = client.get(f"{API_URL}/k8s/events", params=params)
            response.raise_for_status()
            return str(response.json())
    except httpx.HTTPError as e:
        return f"Error getting events: {str(e)}"

# ============================================================
# Phase 2: Intelligent Detection Tools
# ============================================================

@mcp.tool()
def detect_anomalies(namespace: str = None) -> str:
    """
    Detect anomalies in CPU, memory, pod restarts, and pending pods.
    Uses statistical analysis to identify abnormal behavior.
    Args:
        namespace: Optional namespace to scope analysis (None = all namespaces)
    Returns: Comprehensive anomaly report with severity levels and recommendations
    """
    try:
        with httpx.Client(timeout=TIMEOUT * 2) as client:
            params = {"namespace": namespace} if namespace else {}
            response = client.get(f"{API_URL}/detection/anomalies", params=params)
            response.raise_for_status()
            return str(response.json())
    except httpx.HTTPError as e:
        return f"Error detecting anomalies: {str(e)}"

@mcp.tool()
def get_health_score(namespace: str = None) -> str:
    """
    Calculate overall system health score (0-100) based on detected anomalies.
    Provides quick assessment of cluster health with actionable recommendations.
    Args:
        namespace: Optional namespace to scope analysis (None = all namespaces)
    Returns: Health score, status, and top recommendations
    """
    try:
        with httpx.Client(timeout=TIMEOUT * 2) as client:
            params = {"namespace": namespace} if namespace else {}
            response = client.get(f"{API_URL}/detection/health-score", params=params)
            response.raise_for_status()
            return str(response.json())
    except httpx.HTTPError as e:
        return f"Error getting health score: {str(e)}"

@mcp.tool()
def detect_patterns(namespace: str = None) -> str:
    """
    Detect patterns such as recurring pod failures, cyclic CPU spikes, 
    resource exhaustion trends, and cascading failures.
    Args:
        namespace: Optional namespace to scope analysis (None = all namespaces)
    Returns: Detected patterns with confidence levels, occurrences, and recommendations
    """
    try:
        with httpx.Client(timeout=TIMEOUT * 2) as client:
            params = {"namespace": namespace} if namespace else {}
            response = client.get(f"{API_URL}/detection/patterns", params=params)
            response.raise_for_status()
            return str(response.json())
    except httpx.HTTPError as e:
        return f"Error detecting patterns: {str(e)}"

@mcp.tool()
def detect_correlations(namespace: str = None) -> str:
    """
    Correlate metrics, Kubernetes events, and anomalies to identify root causes.
    Links pod restarts with events, CPU spikes with deployments, memory issues with OOMKills.
    Args:
        namespace: Optional namespace to scope analysis (None = all namespaces)
    Returns: Correlation report with confidence scores and impact assessment
    """
    try:
        with httpx.Client(timeout=TIMEOUT * 2) as client:
            params = {"namespace": namespace} if namespace else {}
            response = client.get(f"{API_URL}/detection/correlations", params=params)
            response.raise_for_status()
            return str(response.json())
    except httpx.HTTPError as e:
        return f"Error detecting correlations: {str(e)}"

@mcp.tool()
def comprehensive_analysis(namespace: str = None) -> str:
    """
    Run comprehensive system analysis combining health score, anomaly detection,
    pattern recognition, and correlation analysis in one call.
    Best for getting complete picture of cluster health.
    Args:
        namespace: Optional namespace to scope analysis (None = all namespaces)
    Returns: Complete analysis report with health score, anomalies, patterns, and correlations
    """
    try:
        with httpx.Client(timeout=TIMEOUT * 3) as client:
            params = {"namespace": namespace} if namespace else {}
            response = client.get(f"{API_URL}/detection/comprehensive", params=params)
            response.raise_for_status()
            return str(response.json())
    except httpx.HTTPError as e:
        return f"Error running comprehensive analysis: {str(e)}"

@mcp.tool()
def detect_metric_spike(query: str, duration: str = "1h", spike_multiplier: float = 2.0) -> str:
    """
    Detect sudden spikes in any metric by comparing current value to historical average.
    Args:
        query: PromQL query for the metric to analyze
        duration: Historical period to analyze (e.g., '1h', '6h', '1d')
        spike_multiplier: How many times higher than average to trigger alert (default: 2.0)
    Returns: Detected spikes with Z-scores and deviation from normal
    """
    try:
        with httpx.Client(timeout=TIMEOUT * 2) as client:
            params = {
                "query": query,
                "duration": duration,
                "spike_multiplier": spike_multiplier
            }
            response = client.get(f"{API_URL}/detection/spike", params=params)
            response.raise_for_status()
            return str(response.json())
    except httpx.HTTPError as e:
        return f"Error detecting metric spike: {str(e)}"

def main():
    # IMPORTANT: do not print to stdout in stdio servers
    mcp.run(transport="stdio")

if __name__ == "__main__":
    main()
