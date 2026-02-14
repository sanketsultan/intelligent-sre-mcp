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

def main():
    # IMPORTANT: do not print to stdout in stdio servers
    mcp.run(transport="stdio")

if __name__ == "__main__":
    main()
