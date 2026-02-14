"""
Kubernetes diagnostic tools for intelligent SRE agent.
Provides pod inspection, log retrieval, and health checking capabilities.
"""

from kubernetes import client, config
from kubernetes.client.rest import ApiException
from typing import Dict, List, Optional, Any
import os


class KubernetesTools:
    """Tools for Kubernetes cluster diagnostics and management."""
    
    def __init__(self):
        """Initialize Kubernetes client."""
        try:
            # Try to load in-cluster config first (when running in K8s)
            config.load_incluster_config()
            self.in_cluster = True
        except config.ConfigException:
            # Fall back to kubeconfig (for local development)
            config.load_kube_config()
            self.in_cluster = False
        
        self.v1 = client.CoreV1Api()
        self.apps_v1 = client.AppsV1Api()
        self.batch_v1 = client.BatchV1Api()
    
    def get_all_pods(self, namespace: Optional[str] = None) -> List[Dict[str, Any]]:
        """
        Get all pods with their status.
        
        Args:
            namespace: Specific namespace to query (None = all namespaces)
            
        Returns:
            List of pod information dictionaries
        """
        try:
            if namespace:
                pods = self.v1.list_namespaced_pod(namespace)
            else:
                pods = self.v1.list_pod_for_all_namespaces()
            
            result = []
            for pod in pods.items:
                pod_info = {
                    "name": pod.metadata.name,
                    "namespace": pod.metadata.namespace,
                    "status": pod.status.phase,
                    "node": pod.spec.node_name,
                    "restart_count": sum(
                        c.restart_count for c in (pod.status.container_statuses or [])
                    ),
                    "ready": self._is_pod_ready(pod),
                    "age": self._calculate_age(pod.metadata.creation_timestamp),
                    "containers": len(pod.spec.containers),
                    "ip": pod.status.pod_ip,
                }
                
                # Add reason if pod is not running
                if pod.status.phase != "Running":
                    pod_info["reason"] = self._get_pod_reason(pod)
                
                result.append(pod_info)
            
            return result
        
        except ApiException as e:
            return [{"error": f"Kubernetes API error: {e.status} - {e.reason}"}]
    
    def get_failing_pods(self, namespace: Optional[str] = None) -> List[Dict[str, Any]]:
        """
        Get pods that are in failing states.
        
        Args:
            namespace: Specific namespace to query (None = all namespaces)
            
        Returns:
            List of failing pod information
        """
        all_pods = self.get_all_pods(namespace)
        
        failing_states = ["Failed", "CrashLoopBackOff", "Error", "ImagePullBackOff", 
                         "ErrImagePull", "CreateContainerError", "InvalidImageName"]
        
        failing_pods = []
        for pod in all_pods:
            if "error" in pod:
                return [pod]  # Return error if API call failed
            
            # Check if pod is in failing state
            if (pod["status"] in failing_states or 
                not pod["ready"] or 
                pod["restart_count"] > 5):
                failing_pods.append(pod)
        
        return failing_pods
    
    def get_pod_logs(
        self, 
        namespace: str, 
        pod_name: str, 
        container: Optional[str] = None,
        tail_lines: int = 100,
        previous: bool = False
    ) -> Dict[str, Any]:
        """
        Get logs from a specific pod/container.
        
        Args:
            namespace: Pod namespace
            pod_name: Pod name
            container: Container name (None = first container)
            tail_lines: Number of recent lines to retrieve
            previous: Get logs from previous instance (for crashed containers)
            
        Returns:
            Dictionary with logs or error message
        """
        try:
            # Get pod info to find container name if not specified
            if not container:
                pod = self.v1.read_namespaced_pod(pod_name, namespace)
                if pod.spec.containers:
                    container = pod.spec.containers[0].name
                else:
                    return {"error": "No containers found in pod"}
            
            logs = self.v1.read_namespaced_pod_log(
                name=pod_name,
                namespace=namespace,
                container=container,
                tail_lines=tail_lines,
                previous=previous
            )
            
            return {
                "pod": pod_name,
                "namespace": namespace,
                "container": container,
                "lines": tail_lines,
                "previous": previous,
                "logs": logs
            }
        
        except ApiException as e:
            return {"error": f"Failed to get logs: {e.status} - {e.reason}"}
    
    def describe_pod(self, namespace: str, pod_name: str) -> Dict[str, Any]:
        """
        Get detailed information about a pod (similar to kubectl describe).
        
        Args:
            namespace: Pod namespace
            pod_name: Pod name
            
        Returns:
            Detailed pod information
        """
        try:
            pod = self.v1.read_namespaced_pod(pod_name, namespace)
            events = self.v1.list_namespaced_event(
                namespace,
                field_selector=f"involvedObject.name={pod_name}"
            )
            
            # Extract container statuses
            container_statuses = []
            for container_status in (pod.status.container_statuses or []):
                status_info = {
                    "name": container_status.name,
                    "ready": container_status.ready,
                    "restart_count": container_status.restart_count,
                    "image": container_status.image,
                }
                
                # Get current state
                if container_status.state.running:
                    status_info["state"] = "Running"
                    status_info["started_at"] = str(container_status.state.running.started_at)
                elif container_status.state.waiting:
                    status_info["state"] = "Waiting"
                    status_info["reason"] = container_status.state.waiting.reason
                    status_info["message"] = container_status.state.waiting.message
                elif container_status.state.terminated:
                    status_info["state"] = "Terminated"
                    status_info["reason"] = container_status.state.terminated.reason
                    status_info["exit_code"] = container_status.state.terminated.exit_code
                
                container_statuses.append(status_info)
            
            # Extract recent events
            recent_events = []
            for event in sorted(events.items, key=lambda x: x.last_timestamp or x.event_time, reverse=True)[:10]:
                recent_events.append({
                    "type": event.type,
                    "reason": event.reason,
                    "message": event.message,
                    "count": event.count,
                    "timestamp": str(event.last_timestamp or event.event_time)
                })
            
            return {
                "name": pod.metadata.name,
                "namespace": pod.metadata.namespace,
                "status": pod.status.phase,
                "node": pod.spec.node_name,
                "ip": pod.status.pod_ip,
                "labels": pod.metadata.labels or {},
                "annotations": pod.metadata.annotations or {},
                "containers": container_statuses,
                "conditions": [
                    {
                        "type": cond.type,
                        "status": cond.status,
                        "reason": cond.reason,
                        "message": cond.message
                    }
                    for cond in (pod.status.conditions or [])
                ],
                "events": recent_events,
                "created_at": str(pod.metadata.creation_timestamp)
            }
        
        except ApiException as e:
            return {"error": f"Failed to describe pod: {e.status} - {e.reason}"}
    
    def get_node_status(self) -> List[Dict[str, Any]]:
        """
        Get status of all nodes in the cluster.
        
        Returns:
            List of node information
        """
        try:
            nodes = self.v1.list_node()
            
            result = []
            for node in nodes.items:
                # Get node conditions
                conditions = {}
                for cond in (node.status.conditions or []):
                    conditions[cond.type] = cond.status
                
                node_info = {
                    "name": node.metadata.name,
                    "ready": conditions.get("Ready", "Unknown") == "True",
                    "status": "Ready" if conditions.get("Ready") == "True" else "NotReady",
                    "conditions": conditions,
                    "cpu_capacity": node.status.capacity.get("cpu", "unknown"),
                    "memory_capacity": node.status.capacity.get("memory", "unknown"),
                    "cpu_allocatable": node.status.allocatable.get("cpu", "unknown"),
                    "memory_allocatable": node.status.allocatable.get("memory", "unknown"),
                    "os": node.status.node_info.os_image,
                    "kernel": node.status.node_info.kernel_version,
                    "kubelet_version": node.status.node_info.kubelet_version,
                    "age": self._calculate_age(node.metadata.creation_timestamp)
                }
                
                result.append(node_info)
            
            return result
        
        except ApiException as e:
            return [{"error": f"Failed to get node status: {e.status} - {e.reason}"}]
    
    def get_deployment_status(self, namespace: str, deployment_name: str) -> Dict[str, Any]:
        """
        Get status of a specific deployment.
        
        Args:
            namespace: Deployment namespace
            deployment_name: Deployment name
            
        Returns:
            Deployment status information
        """
        try:
            deployment = self.apps_v1.read_namespaced_deployment(deployment_name, namespace)
            
            return {
                "name": deployment.metadata.name,
                "namespace": deployment.metadata.namespace,
                "replicas": {
                    "desired": deployment.spec.replicas,
                    "current": deployment.status.replicas or 0,
                    "ready": deployment.status.ready_replicas or 0,
                    "available": deployment.status.available_replicas or 0,
                    "unavailable": deployment.status.unavailable_replicas or 0,
                },
                "conditions": [
                    {
                        "type": cond.type,
                        "status": cond.status,
                        "reason": cond.reason,
                        "message": cond.message
                    }
                    for cond in (deployment.status.conditions or [])
                ],
                "strategy": deployment.spec.strategy.type,
                "labels": deployment.metadata.labels or {},
                "created_at": str(deployment.metadata.creation_timestamp)
            }
        
        except ApiException as e:
            return {"error": f"Failed to get deployment status: {e.status} - {e.reason}"}
    
    def get_events(
        self, 
        namespace: Optional[str] = None,
        resource_type: Optional[str] = None,
        resource_name: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """
        Get Kubernetes events.
        
        Args:
            namespace: Filter by namespace (None = all namespaces)
            resource_type: Filter by resource type (Pod, Node, Deployment, etc.)
            resource_name: Filter by resource name
            
        Returns:
            List of events
        """
        try:
            if namespace:
                events = self.v1.list_namespaced_event(namespace)
            else:
                events = self.v1.list_event_for_all_namespaces()
            
            result = []
            for event in events.items:
                # Apply filters
                if resource_type and event.involved_object.kind != resource_type:
                    continue
                if resource_name and event.involved_object.name != resource_name:
                    continue
                
                result.append({
                    "type": event.type,
                    "reason": event.reason,
                    "message": event.message,
                    "count": event.count,
                    "resource_type": event.involved_object.kind,
                    "resource_name": event.involved_object.name,
                    "namespace": event.involved_object.namespace,
                    "timestamp": str(event.last_timestamp or event.event_time)
                })
            
            # Sort by timestamp, most recent first
            result.sort(key=lambda x: x["timestamp"], reverse=True)
            
            return result[:50]  # Return last 50 events
        
        except ApiException as e:
            return [{"error": f"Failed to get events: {e.status} - {e.reason}"}]
    
    # Helper methods
    
    def _is_pod_ready(self, pod) -> bool:
        """Check if pod is ready."""
        if not pod.status.conditions:
            return False
        for condition in pod.status.conditions:
            if condition.type == "Ready":
                return condition.status == "True"
        return False
    
    def _get_pod_reason(self, pod) -> str:
        """Get reason for pod not running."""
        if pod.status.container_statuses:
            for container in pod.status.container_statuses:
                if container.state.waiting:
                    return container.state.waiting.reason
                if container.state.terminated:
                    return container.state.terminated.reason
        return "Unknown"
    
    def _calculate_age(self, creation_timestamp) -> str:
        """Calculate age of resource."""
        from datetime import datetime, timezone
        now = datetime.now(timezone.utc)
        age = now - creation_timestamp
        
        if age.days > 0:
            return f"{age.days}d"
        elif age.seconds > 3600:
            return f"{age.seconds // 3600}h"
        elif age.seconds > 60:
            return f"{age.seconds // 60}m"
        else:
            return f"{age.seconds}s"
