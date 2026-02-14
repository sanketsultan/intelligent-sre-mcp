"""
Self-Healing Actions for Kubernetes
Automated remediation actions with safety mechanisms
"""

import logging
from typing import Dict, Any, List, Optional
from datetime import datetime, timedelta
from kubernetes import client
from kubernetes.client.rest import ApiException
from intelligent_sre_mcp.tools.action_learning import ActionHistoryStore, ActionOutcome

logger = logging.getLogger(__name__)


class HealingActionLimiter:
    """Rate limiting and safety controls for healing actions"""
    
    def __init__(self, action_store: ActionHistoryStore | None = None):
        self.action_history: List[Dict[str, Any]] = []
        self.max_actions_per_hour = 10
        self.max_pods_per_action = 5
        self.cooldown_minutes = 5
        self.action_store = action_store
        
    def can_perform_action(self, action_type: str, affected_resources: int = 1) -> tuple[bool, str]:
        """Check if action is allowed based on safety limits"""
        now = datetime.utcnow()
        one_hour_ago = now - timedelta(hours=1)
        
        # Count recent actions
        recent_actions = [
            a for a in self.action_history 
            if a['timestamp'] > one_hour_ago
        ]
        
        if len(recent_actions) >= self.max_actions_per_hour:
            return False, f"Rate limit exceeded: {len(recent_actions)} actions in last hour (max: {self.max_actions_per_hour})"
        
        # Check blast radius
        if affected_resources > self.max_pods_per_action:
            return False, f"Blast radius too large: {affected_resources} resources (max: {self.max_pods_per_action})"
        
        # Check cooldown for same action type
        same_type_actions = [
            a for a in self.action_history
            if a['action_type'] == action_type and 
               a['timestamp'] > now - timedelta(minutes=self.cooldown_minutes)
        ]
        
        if same_type_actions:
            last_action = same_type_actions[-1]
            cooldown_remaining = self.cooldown_minutes - (now - last_action['timestamp']).total_seconds() / 60
            return False, f"Cooldown active: {cooldown_remaining:.1f} minutes remaining for {action_type}"
        
        return True, "Action allowed"
    
    def record_action(self, action_type: str, namespace: str, resource: str, 
                     success: bool, details: str, problem_id: int | None = None) -> int | None:
        """Record a healing action for audit and rate limiting"""
        self.action_history.append({
            'timestamp': datetime.utcnow(),
            'action_type': action_type,
            'namespace': namespace,
            'resource': resource,
            'success': success,
            'details': details
        })
        
        # Keep only last 24 hours of history
        cutoff = datetime.utcnow() - timedelta(hours=24)
        self.action_history = [
            a for a in self.action_history 
            if a['timestamp'] > cutoff
        ]

        if self.action_store:
            action_id = self.action_store.record_action(
                action_type=action_type,
                namespace=namespace,
                resource=resource,
                success=success,
                details=details,
                problem_id=problem_id,
            )
            self.action_store.record_agent_activity(
                intent="healing_action",
                inputs_summary=f"{action_type} {namespace}/{resource}",
                action_taken=f"{action_type} executed",
                outcome="success" if success else "failed",
                notes=details,
                problem_id=problem_id,
            )
            return action_id
        return None
    
    def get_action_history(self, hours: int = 24) -> List[Dict[str, Any]]:
        """Get action history for the specified time period"""
        cutoff = datetime.utcnow() - timedelta(hours=hours)
        return [
            {
                **a,
                'timestamp': a['timestamp'].isoformat()
            }
            for a in self.action_history
            if a['timestamp'] > cutoff
        ]


class HealingActions:
    """Automated healing actions for Kubernetes resources"""
    
    def __init__(
        self,
        core_api: client.CoreV1Api,
        apps_api: client.AppsV1Api,
        policy_api: client.PolicyV1Api,
        action_store: ActionHistoryStore | None = None
    ):
        self.core_api = core_api
        self.apps_api = apps_api
        self.policy_api = policy_api
        self.action_store = action_store
        self.limiter = HealingActionLimiter(action_store=action_store)
        
    def restart_pod(self, namespace: str, pod_name: str, dry_run: bool = False) -> Dict[str, Any]:
        """
        Restart a pod by deleting it (letting the controller recreate it)
        
        Args:
            namespace: Kubernetes namespace
            pod_name: Name of the pod to restart
            dry_run: If True, only simulate the action
            
        Returns:
            Dict with status and details
        """
        action_type = "restart_pod"
        
        try:
            # Safety check
            allowed, reason = self.limiter.can_perform_action(action_type, affected_resources=1)
            if not allowed:
                return {
                    'success': False,
                    'action': action_type,
                    'namespace': namespace,
                    'resource': pod_name,
                    'error': reason,
                    'dry_run': dry_run
                }
            
            if dry_run:
                logger.info(f"[DRY RUN] Would restart pod {namespace}/{pod_name}")
                return {
                    'success': True,
                    'action': action_type,
                    'namespace': namespace,
                    'resource': pod_name,
                    'message': 'Dry run: Pod would be restarted',
                    'dry_run': True
                }
            
            # Delete the pod (controller will recreate it)
            self.core_api.delete_namespaced_pod(
                name=pod_name,
                namespace=namespace,
                grace_period_seconds=30
            )
            
            action_id = self.limiter.record_action(action_type, namespace, pod_name, True, 
                                                  f"Pod deleted for restart")
            
            logger.info(f"Restarted pod {namespace}/{pod_name}")
            
            return {
                'success': True,
                'action': action_type,
                'namespace': namespace,
                'resource': pod_name,
                'message': 'Pod deleted, controller will recreate it',
                'action_id': action_id,
                'dry_run': False
            }
            
        except ApiException as e:
            error_msg = f"Failed to restart pod: {e.reason}"
            logger.error(error_msg)
            action_id = self.limiter.record_action(action_type, namespace, pod_name, False, error_msg)
            
            return {
                'success': False,
                'action': action_type,
                'namespace': namespace,
                'resource': pod_name,
                'error': error_msg,
                'action_id': action_id,
                'dry_run': dry_run
            }
    
    def delete_failed_pods(self, namespace: str, label_selector: Optional[str] = None, 
                          dry_run: bool = False) -> Dict[str, Any]:
        """
        Delete all pods in Failed, Error, or Completed state
        
        Args:
            namespace: Kubernetes namespace
            label_selector: Optional label selector (e.g., "app=myapp")
            dry_run: If True, only simulate the action
            
        Returns:
            Dict with status and details
        """
        action_type = "delete_failed_pods"
        
        try:
            # Get all pods
            pods = self.core_api.list_namespaced_pod(
                namespace=namespace,
                label_selector=label_selector or ""
            )
            
            # Filter failed/completed pods
            failed_pods = [
                pod for pod in pods.items
                if pod.status.phase in ['Failed', 'Succeeded', 'Unknown']
            ]
            
            if not failed_pods:
                return {
                    'success': True,
                    'action': action_type,
                    'namespace': namespace,
                    'message': 'No failed pods found',
                    'deleted_count': 0,
                    'dry_run': dry_run
                }
            
            # Safety check
            allowed, reason = self.limiter.can_perform_action(
                action_type, 
                affected_resources=len(failed_pods)
            )
            if not allowed:
                return {
                    'success': False,
                    'action': action_type,
                    'namespace': namespace,
                    'error': reason,
                    'found_pods': len(failed_pods),
                    'dry_run': dry_run
                }
            
            deleted_pods = []
            
            if dry_run:
                logger.info(f"[DRY RUN] Would delete {len(failed_pods)} failed pods in {namespace}")
                return {
                    'success': True,
                    'action': action_type,
                    'namespace': namespace,
                    'message': f'Dry run: Would delete {len(failed_pods)} failed pods',
                    'pods': [pod.metadata.name for pod in failed_pods],
                    'deleted_count': len(failed_pods),
                    'dry_run': True
                }
            
            # Delete each failed pod
            for pod in failed_pods:
                try:
                    self.core_api.delete_namespaced_pod(
                        name=pod.metadata.name,
                        namespace=namespace,
                        grace_period_seconds=0
                    )
                    deleted_pods.append(pod.metadata.name)
                except ApiException as e:
                    logger.error(f"Failed to delete pod {pod.metadata.name}: {e.reason}")
            
            action_id = self.limiter.record_action(action_type, namespace, f"{len(deleted_pods)} pods", 
                                                  True, f"Deleted {len(deleted_pods)} failed pods")
            
            logger.info(f"Deleted {len(deleted_pods)} failed pods in {namespace}")
            
            return {
                'success': True,
                'action': action_type,
                'namespace': namespace,
                'message': f'Deleted {len(deleted_pods)} failed pods',
                'deleted_pods': deleted_pods,
                'deleted_count': len(deleted_pods),
                'action_id': action_id,
                'dry_run': False
            }
            
        except ApiException as e:
            error_msg = f"Failed to delete failed pods: {e.reason}"
            logger.error(error_msg)
            action_id = self.limiter.record_action(action_type, namespace, "multiple", False, error_msg)
            
            return {
                'success': False,
                'action': action_type,
                'namespace': namespace,
                'error': error_msg,
                'action_id': action_id,
                'dry_run': dry_run
            }

    def evict_pod_from_node(self, namespace: str, pod_name: str, dry_run: bool = False,
                           grace_period_seconds: int = 30) -> Dict[str, Any]:
        """
        Evict a pod from its node (uses the eviction API)
        
        Args:
            namespace: Kubernetes namespace
            pod_name: Name of the pod to evict
            dry_run: If True, only simulate the action
            grace_period_seconds: Grace period before eviction
            
        Returns:
            Dict with status and details
        """
        action_type = "evict_pod_from_node"
        
        try:
            allowed, reason = self.limiter.can_perform_action(action_type, affected_resources=1)
            if not allowed:
                return {
                    'success': False,
                    'action': action_type,
                    'namespace': namespace,
                    'resource': pod_name,
                    'error': reason,
                    'dry_run': dry_run
                }
            
            if dry_run:
                logger.info(f"[DRY RUN] Would evict pod {namespace}/{pod_name}")
                return {
                    'success': True,
                    'action': action_type,
                    'namespace': namespace,
                    'resource': pod_name,
                    'message': 'Dry run: Pod would be evicted from its node',
                    'dry_run': True
                }
            
            eviction = client.V1Eviction(
                metadata=client.V1ObjectMeta(name=pod_name, namespace=namespace),
                delete_options=client.V1DeleteOptions(grace_period_seconds=grace_period_seconds)
            )
            
            self.policy_api.create_namespaced_pod_eviction(
                name=pod_name,
                namespace=namespace,
                body=eviction
            )
            
            action_id = self.limiter.record_action(action_type, namespace, pod_name, True, "Pod evicted")
            
            logger.info(f"Evicted pod {namespace}/{pod_name}")
            
            return {
                'success': True,
                'action': action_type,
                'namespace': namespace,
                'resource': pod_name,
                'message': 'Pod eviction requested successfully',
                'action_id': action_id,
                'dry_run': False
            }
            
        except ApiException as e:
            error_msg = f"Failed to evict pod: {e.reason}"
            logger.error(error_msg)
            action_id = self.limiter.record_action(action_type, namespace, pod_name, False, error_msg)
            
            return {
                'success': False,
                'action': action_type,
                'namespace': namespace,
                'resource': pod_name,
                'error': error_msg,
                'action_id': action_id,
                'dry_run': dry_run
            }

    def drain_node(self, node_name: str, dry_run: bool = False, grace_period_seconds: int = 30,
                   ignore_daemonsets: bool = True, include_kube_system: bool = False) -> Dict[str, Any]:
        """
        Drain a node by evicting all non-daemonset pods
        
        Args:
            node_name: Name of the node to drain
            dry_run: If True, only simulate the action
            grace_period_seconds: Grace period before eviction
            ignore_daemonsets: If True, skip pods owned by DaemonSets
            include_kube_system: If True, include kube-system pods
            
        Returns:
            Dict with status and details
        """
        action_type = "drain_node"
        
        try:
            pods = self.core_api.list_pod_for_all_namespaces(
                field_selector=f"spec.nodeName={node_name}"
            )
            
            evictable_pods = []
            skipped_pods = []
            
            for pod in pods.items:
                namespace = pod.metadata.namespace
                
                if not include_kube_system and namespace == "kube-system":
                    skipped_pods.append(f"{namespace}/{pod.metadata.name}")
                    continue
                
                if pod.metadata.annotations and pod.metadata.annotations.get("kubernetes.io/config.mirror"):
                    skipped_pods.append(f"{namespace}/{pod.metadata.name}")
                    continue
                
                if ignore_daemonsets and pod.metadata.owner_references:
                    if any(owner.kind == "DaemonSet" for owner in pod.metadata.owner_references):
                        skipped_pods.append(f"{namespace}/{pod.metadata.name}")
                        continue
                
                evictable_pods.append(pod)
            
            if not evictable_pods:
                return {
                    'success': True,
                    'action': action_type,
                    'resource': node_name,
                    'message': 'No evictable pods found on node',
                    'evicted_count': 0,
                    'skipped_pods': skipped_pods,
                    'dry_run': dry_run
                }
            
            allowed, reason = self.limiter.can_perform_action(action_type, affected_resources=len(evictable_pods))
            if dry_run:
                logger.info(f"[DRY RUN] Would drain node {node_name} ({len(evictable_pods)} pods)")
                return {
                    'success': True,
                    'action': action_type,
                    'resource': node_name,
                    'message': f'Dry run: Would evict {len(evictable_pods)} pods from node',
                    'pods': [f"{pod.metadata.namespace}/{pod.metadata.name}" for pod in evictable_pods],
                    'evicted_count': len(evictable_pods),
                    'skipped_pods': skipped_pods,
                    'would_be_blocked': not allowed,
                    'block_reason': reason if not allowed else None,
                    'dry_run': True
                }
            
            if not allowed:
                return {
                    'success': False,
                    'action': action_type,
                    'resource': node_name,
                    'error': reason,
                    'found_pods': len(evictable_pods),
                    'dry_run': dry_run
                }
            
            evicted = []
            failed = []
            
            for pod in evictable_pods:
                pod_namespace = pod.metadata.namespace
                pod_name = pod.metadata.name
                try:
                    eviction = client.V1Eviction(
                        metadata=client.V1ObjectMeta(name=pod_name, namespace=pod_namespace),
                        delete_options=client.V1DeleteOptions(grace_period_seconds=grace_period_seconds)
                    )
                    self.policy_api.create_namespaced_pod_eviction(
                        name=pod_name,
                        namespace=pod_namespace,
                        body=eviction
                    )
                    evicted.append(f"{pod_namespace}/{pod_name}")
                except ApiException as e:
                    logger.error(f"Failed to evict pod {pod_namespace}/{pod_name}: {e.reason}")
                    failed.append({
                        "pod": f"{pod_namespace}/{pod_name}",
                        "error": e.reason
                    })
            
            action_id = self.limiter.record_action(action_type, "-", node_name, True,
                                                  f"Evicted {len(evicted)} pods from node")
            
            logger.info(f"Drained node {node_name}: evicted {len(evicted)} pods")
            
            return {
                'success': True,
                'action': action_type,
                'resource': node_name,
                'message': f'Evicted {len(evicted)} pods from node',
                'evicted_pods': evicted,
                'evicted_count': len(evicted),
                'failed_evictions': failed,
                'skipped_pods': skipped_pods,
                'action_id': action_id,
                'dry_run': False
            }
            
        except ApiException as e:
            error_msg = f"Failed to drain node: {e.reason}"
            logger.error(error_msg)
            action_id = self.limiter.record_action(action_type, "-", node_name, False, error_msg)
            
            return {
                'success': False,
                'action': action_type,
                'resource': node_name,
                'error': error_msg,
                'action_id': action_id,
                'dry_run': dry_run
            }
    
    def scale_deployment(self, namespace: str, deployment_name: str, 
                        replicas: int, dry_run: bool = False) -> Dict[str, Any]:
        """
        Scale a deployment to the specified number of replicas
        
        Args:
            namespace: Kubernetes namespace
            deployment_name: Name of the deployment
            replicas: Target number of replicas
            dry_run: If True, only simulate the action
            
        Returns:
            Dict with status and details
        """
        action_type = "scale_deployment"
        
        try:
            # Get current deployment
            deployment = self.apps_api.read_namespaced_deployment(
                name=deployment_name,
                namespace=namespace
            )
            
            current_replicas = deployment.spec.replicas
            
            if current_replicas == replicas:
                return {
                    'success': True,
                    'action': action_type,
                    'namespace': namespace,
                    'resource': deployment_name,
                    'message': f'Deployment already at {replicas} replicas',
                    'current_replicas': current_replicas,
                    'target_replicas': replicas,
                    'dry_run': dry_run
                }
            
            # Safety check
            affected_resources = abs(replicas - current_replicas)
            allowed, reason = self.limiter.can_perform_action(action_type, affected_resources)
            if not allowed:
                return {
                    'success': False,
                    'action': action_type,
                    'namespace': namespace,
                    'resource': deployment_name,
                    'error': reason,
                    'dry_run': dry_run
                }
            
            if dry_run:
                logger.info(f"[DRY RUN] Would scale {namespace}/{deployment_name} from {current_replicas} to {replicas}")
                return {
                    'success': True,
                    'action': action_type,
                    'namespace': namespace,
                    'resource': deployment_name,
                    'message': f'Dry run: Would scale from {current_replicas} to {replicas} replicas',
                    'current_replicas': current_replicas,
                    'target_replicas': replicas,
                    'dry_run': True
                }
            
            # Scale the deployment
            deployment.spec.replicas = replicas
            self.apps_api.patch_namespaced_deployment(
                name=deployment_name,
                namespace=namespace,
                body=deployment
            )
            
            action_id = self.limiter.record_action(action_type, namespace, deployment_name, True,
                                                  f"Scaled from {current_replicas} to {replicas}")
            
            logger.info(f"Scaled deployment {namespace}/{deployment_name} from {current_replicas} to {replicas}")
            
            return {
                'success': True,
                'action': action_type,
                'namespace': namespace,
                'resource': deployment_name,
                'message': f'Scaled from {current_replicas} to {replicas} replicas',
                'previous_replicas': current_replicas,
                'current_replicas': replicas,
                'action_id': action_id,
                'dry_run': False
            }
            
        except ApiException as e:
            error_msg = f"Failed to scale deployment: {e.reason}"
            logger.error(error_msg)
            action_id = self.limiter.record_action(action_type, namespace, deployment_name, False, error_msg)
            
            return {
                'success': False,
                'action': action_type,
                'namespace': namespace,
                'resource': deployment_name,
                'error': error_msg,
                'action_id': action_id,
                'dry_run': dry_run
            }
    
    def rollback_deployment(self, namespace: str, deployment_name: str, 
                           revision: Optional[int] = None, dry_run: bool = False) -> Dict[str, Any]:
        """
        Rollback a deployment to a previous revision
        
        Args:
            namespace: Kubernetes namespace
            deployment_name: Name of the deployment
            revision: Specific revision to rollback to (None = previous)
            dry_run: If True, only simulate the action
            
        Returns:
            Dict with status and details
        """
        action_type = "rollback_deployment"
        
        try:
            # Safety check
            allowed, reason = self.limiter.can_perform_action(action_type, affected_resources=1)
            if not allowed:
                return {
                    'success': False,
                    'action': action_type,
                    'namespace': namespace,
                    'resource': deployment_name,
                    'error': reason,
                    'dry_run': dry_run
                }
            
            if dry_run:
                revision_msg = f"revision {revision}" if revision else "previous revision"
                logger.info(f"[DRY RUN] Would rollback {namespace}/{deployment_name} to {revision_msg}")
                return {
                    'success': True,
                    'action': action_type,
                    'namespace': namespace,
                    'resource': deployment_name,
                    'message': f'Dry run: Would rollback to {revision_msg}',
                    'target_revision': revision,
                    'dry_run': True
                }
            
            # Get deployment
            deployment = self.apps_api.read_namespaced_deployment(
                name=deployment_name,
                namespace=namespace
            )
            
            # Trigger rollback by updating deployment with rollback annotation
            if deployment.metadata.annotations is None:
                deployment.metadata.annotations = {}
            
            deployment.metadata.annotations['deployment.kubernetes.io/revision'] = str(revision or 0)
            
            self.apps_api.patch_namespaced_deployment(
                name=deployment_name,
                namespace=namespace,
                body=deployment
            )
            
            revision_msg = f"revision {revision}" if revision else "previous revision"
            action_id = self.limiter.record_action(action_type, namespace, deployment_name, True,
                                                  f"Rolled back to {revision_msg}")
            
            logger.info(f"Rolled back deployment {namespace}/{deployment_name} to {revision_msg}")
            
            return {
                'success': True,
                'action': action_type,
                'namespace': namespace,
                'resource': deployment_name,
                'message': f'Rolled back to {revision_msg}',
                'target_revision': revision,
                'action_id': action_id,
                'dry_run': False
            }
            
        except ApiException as e:
            error_msg = f"Failed to rollback deployment: {e.reason}"
            logger.error(error_msg)
            action_id = self.limiter.record_action(action_type, namespace, deployment_name, False, error_msg)
            
            return {
                'success': False,
                'action': action_type,
                'namespace': namespace,
                'resource': deployment_name,
                'error': error_msg,
                'action_id': action_id,
                'dry_run': dry_run
            }
    
    def cordon_node(self, node_name: str, dry_run: bool = False) -> Dict[str, Any]:
        """
        Cordon a node (mark as unschedulable)
        
        Args:
            node_name: Name of the node
            dry_run: If True, only simulate the action
            
        Returns:
            Dict with status and details
        """
        action_type = "cordon_node"
        
        try:
            # Safety check
            allowed, reason = self.limiter.can_perform_action(action_type, affected_resources=1)
            if not allowed:
                return {
                    'success': False,
                    'action': action_type,
                    'resource': node_name,
                    'error': reason,
                    'dry_run': dry_run
                }
            
            if dry_run:
                logger.info(f"[DRY RUN] Would cordon node {node_name}")
                return {
                    'success': True,
                    'action': action_type,
                    'resource': node_name,
                    'message': f'Dry run: Would mark node {node_name} as unschedulable',
                    'dry_run': True
                }
            
            # Get node
            node = self.core_api.read_node(name=node_name)
            
            if node.spec.unschedulable:
                return {
                    'success': True,
                    'action': action_type,
                    'resource': node_name,
                    'message': f'Node {node_name} is already cordoned',
                    'dry_run': False
                }
            
            # Cordon the node
            node.spec.unschedulable = True
            self.core_api.patch_node(name=node_name, body=node)
            
            action_id = self.limiter.record_action(action_type, "-", node_name, True, "Node cordoned")
            
            logger.info(f"Cordoned node {node_name}")
            
            return {
                'success': True,
                'action': action_type,
                'resource': node_name,
                'message': f'Node {node_name} marked as unschedulable',
                'action_id': action_id,
                'dry_run': False
            }
            
        except ApiException as e:
            error_msg = f"Failed to cordon node: {e.reason}"
            logger.error(error_msg)
            action_id = self.limiter.record_action(action_type, "-", node_name, False, error_msg)
            
            return {
                'success': False,
                'action': action_type,
                'resource': node_name,
                'error': error_msg,
                'action_id': action_id,
                'dry_run': dry_run
            }
    
    def uncordon_node(self, node_name: str, dry_run: bool = False) -> Dict[str, Any]:
        """
        Uncordon a node (mark as schedulable)
        
        Args:
            node_name: Name of the node
            dry_run: If True, only simulate the action
            
        Returns:
            Dict with status and details
        """
        action_type = "uncordon_node"
        
        try:
            if dry_run:
                logger.info(f"[DRY RUN] Would uncordon node {node_name}")
                return {
                    'success': True,
                    'action': action_type,
                    'resource': node_name,
                    'message': f'Dry run: Would mark node {node_name} as schedulable',
                    'dry_run': True
                }
            
            # Get node
            node = self.core_api.read_node(name=node_name)
            
            if not node.spec.unschedulable:
                return {
                    'success': True,
                    'action': action_type,
                    'resource': node_name,
                    'message': f'Node {node_name} is already schedulable',
                    'dry_run': False
                }
            
            # Uncordon the node
            node.spec.unschedulable = False
            self.core_api.patch_node(name=node_name, body=node)
            
            action_id = self.limiter.record_action(action_type, "-", node_name, True, "Node uncordoned")
            logger.info(f"Uncordoned node {node_name}")
            
            return {
                'success': True,
                'action': action_type,
                'resource': node_name,
                'message': f'Node {node_name} marked as schedulable',
                'action_id': action_id,
                'dry_run': False
            }
            
        except ApiException as e:
            error_msg = f"Failed to uncordon node: {e.reason}"
            logger.error(error_msg)
            
            action_id = self.limiter.record_action(action_type, "-", node_name, False, error_msg)
            return {
                'success': False,
                'action': action_type,
                'resource': node_name,
                'error': error_msg,
                'action_id': action_id,
                'dry_run': dry_run
            }
    
    def get_action_history(self, hours: int = 24) -> Dict[str, Any]:
        """Get healing action history"""
        if self.action_store:
            return self.action_store.history_summary(hours)
        history = self.limiter.get_action_history(hours)
        
        total_actions = len(history)
        successful_actions = sum(1 for a in history if a['success'])
        failed_actions = total_actions - successful_actions
        
        action_types = {}
        for action in history:
            action_type = action['action_type']
            if action_type not in action_types:
                action_types[action_type] = {'total': 0, 'success': 0, 'failed': 0}
            
            action_types[action_type]['total'] += 1
            if action['success']:
                action_types[action_type]['success'] += 1
            else:
                action_types[action_type]['failed'] += 1
        
        return {
            'time_period_hours': hours,
            'total_actions': total_actions,
            'successful_actions': successful_actions,
            'failed_actions': failed_actions,
            'success_rate': round(successful_actions / total_actions * 100, 1) if total_actions > 0 else 0,
            'by_action_type': action_types,
            'recent_actions': history[-10:] if history else []
        }

    def get_action_stats(self, hours: int = 24) -> Dict[str, Any]:
        if not self.action_store:
            return {"error": "Action history store not configured"}
        return self.action_store.action_stats(hours)

    def get_recurring_issues(self, hours: int = 24, min_count: int = 2) -> Dict[str, Any]:
        if not self.action_store:
            return {"error": "Action history store not configured"}
        return {
            "time_period_hours": hours,
            "min_count": min_count,
            "recurring_issues": self.action_store.recurring_issues(hours, min_count)
        }

    def record_action_outcome(
        self,
        action_id: int,
        outcome: str,
        resolution_time_seconds: float | None = None,
        notes: str | None = None
    ) -> Dict[str, Any]:
        if not self.action_store:
            return {"success": False, "error": "Action history store not configured"}
        updated = self.action_store.update_outcome(
            ActionOutcome(
                action_id=action_id,
                outcome=outcome,
                resolution_time_seconds=resolution_time_seconds,
                notes=notes
            )
        )
        return {"success": updated, "action_id": action_id}
