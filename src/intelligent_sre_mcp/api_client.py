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

# ============================================================
# Phase 5: Learning & Optimization (29 tools total)
# ============================================================

@mcp.tool()
def restart_pod(namespace: str, pod_name: str, dry_run: bool = False) -> str:
    """
    Restart a Kubernetes pod by deleting it (controller will recreate).
    
    ⚠️  CRITICAL WORKFLOW - ALWAYS FOLLOW THIS ORDER:
    1. FIRST: Use describe_pod() to check WHY the pod is failing
    2. SECOND: Check pod logs with k8s_get_pod_logs() to see errors
    3. THIRD: Analyze if restart will help or if config/image needs fixing
    4. FOURTH: Use dry_run=True to preview the restart
    5. FINALLY: Only restart if diagnosis shows it will help
    
    WHEN TO USE: Only for CrashLoopBackOff, temporary issues, or stuck pods.
    WHEN NOT TO USE: Image pull errors, config issues, resource limits - fix root cause instead!
    
    Args:
        namespace: Pod namespace
        pod_name: Pod name to restart
        dry_run: If True, only simulate the action (default: False)
    Returns: Action result with success status
    """
    try:
        with httpx.Client(timeout=TIMEOUT) as client:
            params = {
                "namespace": namespace,
                "pod_name": pod_name,
                "dry_run": dry_run
            }
            response = client.post(f"{API_URL}/healing/restart-pod", params=params)
            response.raise_for_status()
            return str(response.json())
    except httpx.HTTPError as e:
        return f"Error restarting pod: {str(e)}"

@mcp.tool()
def delete_failed_pods(namespace: str, label_selector: str = None, dry_run: bool = False) -> str:
    """
    Delete pods in Failed, Succeeded, or Unknown state (cleanup only).
    
    ⚠️  CRITICAL WORKFLOW - ALWAYS FOLLOW THIS ORDER:
    1. FIRST: Use k8s_get_all_pods() to see which pods are failed
    2. SECOND: Use describe_pod() on EACH failed pod to understand WHY it failed
    3. THIRD: Check if it's a recurring issue or one-time failure
    4. FOURTH: Use dry_run=True to preview which pods will be deleted
    5. FINALLY: Only delete if you've diagnosed the root cause
    
    WHEN TO USE: Cleaning up completed jobs, one-time failures already investigated.
    WHEN NOT TO USE: Active troubleshooting - investigate first! Don't delete evidence!
    
    NOTE: This is for CLEANUP, not fixing problems. Fix root cause first!
    
    Args:
        namespace: Namespace to clean up
        label_selector: Optional label selector (e.g., 'app=myapp')
        dry_run: If True, only simulate the action (default: False)
    Returns: List of deleted pods and count
    """
    try:
        with httpx.Client(timeout=TIMEOUT) as client:
            params = {
                "namespace": namespace,
                "dry_run": dry_run
            }
            if label_selector:
                params["label_selector"] = label_selector
            response = client.post(f"{API_URL}/healing/delete-failed-pods", params=params)
            response.raise_for_status()
            return str(response.json())
    except httpx.HTTPError as e:
        return f"Error deleting failed pods: {str(e)}"

@mcp.tool()
def evict_pod_from_node(namespace: str, pod_name: str, dry_run: bool = False, grace_period_seconds: int = 30) -> str:
    """
    Evict a pod from its node using the eviction API.
    
    ⚠️  CRITICAL WORKFLOW - ALWAYS FOLLOW THIS ORDER:
    1. FIRST: Use describe_pod() to confirm the pod is on the target node
    2. SECOND: Check pod logs and events for root cause
    3. THIRD: Verify eviction won't break availability (check replicas/PodDisruptionBudget)
    4. FOURTH: Use dry_run=True to preview the eviction
    5. FINALLY: Only evict if diagnosis shows it's safe and necessary
    
    WHEN TO USE: Node issues, noisy neighbor, maintenance, rescheduling
    WHEN NOT TO USE: Single-replica critical pods without redundancy
    
    Args:
        namespace: Pod namespace
        pod_name: Pod name to evict
        dry_run: If True, only simulate the action (default: False)
        grace_period_seconds: Grace period before eviction (default: 30)
    Returns: Eviction result
    """
    try:
        with httpx.Client(timeout=TIMEOUT) as client:
            params = {
                "namespace": namespace,
                "pod_name": pod_name,
                "dry_run": dry_run,
                "grace_period_seconds": grace_period_seconds
            }
            response = client.post(f"{API_URL}/healing/evict-pod", params=params)
            response.raise_for_status()
            return str(response.json())
    except httpx.HTTPError as e:
        return f"Error evicting pod: {str(e)}"

@mcp.tool()
def drain_node(
    node_name: str,
    dry_run: bool = False,
    grace_period_seconds: int = 30,
    ignore_daemonsets: bool = True,
    include_kube_system: bool = False
) -> str:
    """
    Drain a node by evicting all non-daemonset pods.
    
    ⚠️  CRITICAL WORKFLOW - ALWAYS FOLLOW THIS ORDER:
    1. FIRST: Use k8s_get_node() to confirm node status/conditions
    2. SECOND: Check what pods are running and their redundancy
    3. THIRD: Cordon the node before draining
    4. FOURTH: Use dry_run=True to preview which pods will be evicted
    5. FINALLY: Drain only if it won't violate availability
    
    WHEN TO USE: Planned maintenance, node instability, upgrades
    WHEN NOT TO USE: Production incidents without redundancy or approval
    
    Args:
        node_name: Node name to drain
        dry_run: If True, only simulate the action (default: False)
        grace_period_seconds: Grace period before eviction (default: 30)
        ignore_daemonsets: Skip DaemonSet pods (default: True)
        include_kube_system: Include kube-system pods (default: False)
    Returns: Drain result
    """
    try:
        with httpx.Client(timeout=TIMEOUT) as client:
            params = {
                "node_name": node_name,
                "dry_run": dry_run,
                "grace_period_seconds": grace_period_seconds,
                "ignore_daemonsets": ignore_daemonsets,
                "include_kube_system": include_kube_system
            }
            response = client.post(f"{API_URL}/healing/drain-node", params=params)
            response.raise_for_status()
            return str(response.json())
    except httpx.HTTPError as e:
        return f"Error draining node: {str(e)}"

@mcp.tool()
def scale_deployment(namespace: str, deployment_name: str, replicas: int, dry_run: bool = False) -> str:
    """
    Scale a deployment to a specific number of replicas.
    
    ⚠️  CRITICAL WORKFLOW - ALWAYS FOLLOW THIS ORDER:
    1. FIRST: Use k8s_get_deployment() to check current replicas and status
    2. SECOND: Use get_health_score() to see if there are underlying issues
    3. THIRD: Analyze WHY scaling is needed (high load? failures? testing?)
    4. FOURTH: Use dry_run=True to preview the scaling action
    5. FINALLY: Scale only if diagnosis shows it's the right solution
    
    WHEN TO USE: High load, capacity planning, intentional scaling.
    WHEN NOT TO USE: If pods are crashing - fix the crashes first, not scale!
    
    Args:
        namespace: Deployment namespace
        deployment_name: Deployment name
        replicas: Target number of replicas
        dry_run: If True, only simulate the action (default: False)
    Returns: Scaling result with previous and current replica count
    """
    try:
        with httpx.Client(timeout=TIMEOUT) as client:
            params = {
                "namespace": namespace,
                "deployment_name": deployment_name,
                "replicas": replicas,
                "dry_run": dry_run
            }
            response = client.post(f"{API_URL}/healing/scale-deployment", params=params)
            response.raise_for_status()
            return str(response.json())
    except httpx.HTTPError as e:
        return f"Error scaling deployment: {str(e)}"

@mcp.tool()
def rollback_deployment(namespace: str, deployment_name: str, revision: int = None, dry_run: bool = False) -> str:
    """
    Rollback a deployment to a previous revision.
    
    ⚠️  CRITICAL WORKFLOW - ALWAYS FOLLOW THIS ORDER:
    1. FIRST: Use k8s_get_deployment() to check current revision and status
    2. SECOND: Check deployment history to see what changed
    3. THIRD: Analyze if rollback will fix the issue or if it's environmental
    4. FOURTH: Use dry_run=True to preview the rollback
    5. FINALLY: Only rollback if diagnosis confirms it will help
    
    WHEN TO USE: Bad deployment, new version causing issues
    WHEN NOT TO USE: Infrastructure issues, config problems - fix root cause!
    
    NOTE: Rollback is temporary - fix the actual code/config issue!
    
    Args:
        namespace: Deployment namespace
        deployment_name: Deployment name
        revision: Specific revision to rollback to (None = previous revision)
        dry_run: If True, only simulate the action (default: False)
    Returns: Rollback result
    """
    try:
        with httpx.Client(timeout=TIMEOUT) as client:
            params = {
                "namespace": namespace,
                "deployment_name": deployment_name,
                "dry_run": dry_run
            }
            if revision is not None:
                params["revision"] = revision
            response = client.post(f"{API_URL}/healing/rollback-deployment", params=params)
            response.raise_for_status()
            return str(response.json())
    except httpx.HTTPError as e:
        return f"Error rolling back deployment: {str(e)}"

@mcp.tool()
def cordon_node(node_name: str, dry_run: bool = False) -> str:
    """
    Cordon a node (mark as unschedulable - prevents new pods from being scheduled).
    
    ⚠️  CRITICAL WORKFLOW - ALWAYS FOLLOW THIS ORDER:
    1. FIRST: Use k8s_get_node() to check node status and conditions
    2. SECOND: Check if node has issues (DiskPressure, MemoryPressure, etc.)
    3. THIRD: Analyze if cordoning is necessary or if node will recover
    4. FOURTH: Check what pods are running on this node
    5. FIFTH: Use dry_run=True to preview
    6. FINALLY: Only cordon if diagnosis shows node is problematic
    
    WHEN TO USE: Planned maintenance, failing node, draining for updates
    WHEN NOT TO USE: Normal operation - don't cordon healthy nodes!
    
    NOTE: Cordoning doesn't evict existing pods - use drain for that!
    
    Args:
        node_name: Node name to cordon
        dry_run: If True, only simulate the action (default: False)
    Returns: Cordon result
    """
    try:
        with httpx.Client(timeout=TIMEOUT) as client:
            params = {
                "node_name": node_name,
                "dry_run": dry_run
            }
            response = client.post(f"{API_URL}/healing/cordon-node", params=params)
            response.raise_for_status()
            return str(response.json())
    except httpx.HTTPError as e:
        return f"Error cordoning node: {str(e)}"

@mcp.tool()
def uncordon_node(node_name: str, dry_run: bool = False) -> str:
    """
    Uncordon a node (mark as schedulable - allows new pods to be scheduled).
    
    ⚠️  CRITICAL WORKFLOW - ALWAYS FOLLOW THIS ORDER:
    1. FIRST: Use k8s_get_node() to verify node is Ready
    2. SECOND: Check node conditions are healthy (no DiskPressure, MemoryPressure)
    3. THIRD: Verify the original issue that caused cordoning is resolved
    4. FOURTH: Use dry_run=True to preview
    5. FINALLY: Only uncordon if node is confirmed healthy
    
    WHEN TO USE: After maintenance complete, after node recovery, after updates
    WHEN NOT TO USE: If node still has issues - fix them first!
    
    NOTE: Uncordoning immediately allows scheduling - ensure node is ready!
    
    Args:
        node_name: Node name to uncordon
        dry_run: If True, only simulate the action (default: False)
    Returns: Uncordon result
    """
    try:
        with httpx.Client(timeout=TIMEOUT) as client:
            params = {
                "node_name": node_name,
                "dry_run": dry_run
            }
            response = client.post(f"{API_URL}/healing/uncordon-node", params=params)
            response.raise_for_status()
            return str(response.json())
    except httpx.HTTPError as e:
        return f"Error uncordoning node: {str(e)}"

@mcp.tool()
def get_healing_history(hours: int = 24) -> str:
    """
    Get history of all healing actions taken by the system.
    Args:
        hours: Number of hours of history to retrieve (default: 24)
    Returns: Action history with statistics and recent actions
    """
    try:
        with httpx.Client(timeout=TIMEOUT) as client:
            params = {"hours": hours}
            response = client.get(f"{API_URL}/healing/action-history", params=params)
            response.raise_for_status()
            return str(response.json())
    except httpx.HTTPError as e:
        return f"Error getting healing history: {str(e)}"

@mcp.tool()
def get_action_stats(hours: int = 24) -> str:
    """
    Get healing action effectiveness statistics.
    Args:
        hours: Number of hours of history to analyze (default: 24)
    Returns: Action stats with success rates and averages
    """
    try:
        with httpx.Client(timeout=TIMEOUT) as client:
            params = {"hours": hours}
            response = client.get(f"{API_URL}/learning/action-stats", params=params)
            response.raise_for_status()
            return str(response.json())
    except httpx.HTTPError as e:
        return f"Error getting action stats: {str(e)}"

@mcp.tool()
def get_recurring_issues(hours: int = 24, min_count: int = 2) -> str:
    """
    Identify recurring issues based on healing actions.
    Args:
        hours: Number of hours of history to analyze (default: 24)
        min_count: Minimum occurrences to consider recurring (default: 2)
    Returns: Recurring issues grouped by resource and action type
    """
    try:
        with httpx.Client(timeout=TIMEOUT) as client:
            params = {"hours": hours, "min_count": min_count}
            response = client.get(f"{API_URL}/learning/recurring-issues", params=params)
            response.raise_for_status()
            return str(response.json())
    except httpx.HTTPError as e:
        return f"Error getting recurring issues: {str(e)}"

@mcp.tool()
def record_action_outcome(action_id: int, outcome: str, resolution_time_seconds: float = None, notes: str = None) -> str:
    """
    Record the outcome and resolution time for a healing action.
    Args:
        action_id: Action ID returned by a healing action
        outcome: Outcome label (e.g., success, partial, failed)
        resolution_time_seconds: Time to recovery in seconds (optional)
        notes: Optional notes about the outcome
    Returns: Outcome recording result
    """
    try:
        with httpx.Client(timeout=TIMEOUT) as client:
            payload = {
                "action_id": action_id,
                "outcome": outcome,
                "resolution_time_seconds": resolution_time_seconds,
                "notes": notes
            }
            response = client.post(f"{API_URL}/learning/record-outcome", json=payload)
            response.raise_for_status()
            return str(response.json())
    except httpx.HTTPError as e:
        return f"Error recording action outcome: {str(e)}"

def main():
    # IMPORTANT: do not print to stdout in stdio servers
    mcp.run(transport="stdio")

if __name__ == "__main__":
    main()
