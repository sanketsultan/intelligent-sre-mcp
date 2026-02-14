"""
Correlation Engine
Correlates metrics, Kubernetes events, and alerts to provide holistic insights.
"""

import os
import httpx
from typing import Dict, List, Optional, Any, Tuple
from datetime import datetime, timedelta
from dataclasses import dataclass
from enum import Enum
from collections import defaultdict

# Import K8s tools for event correlation
try:
    from intelligent_sre_mcp.tools.k8s_tools import KubernetesTools
except ImportError:
    KubernetesTools = None


class CorrelationType(str, Enum):
    """Types of correlations that can be detected"""
    METRIC_TO_EVENT = "metric_to_event"
    EVENT_TO_METRIC = "event_to_metric"
    CASCADING = "cascading"
    TIME_BASED = "time_based"


@dataclass
class Correlation:
    """Represents a detected correlation between different signals"""
    correlation_type: CorrelationType
    description: str
    confidence: float  # 0.0 to 1.0
    timestamp: str
    primary_signal: Dict[str, Any]
    related_signals: List[Dict[str, Any]]
    recommendation: str
    impact_score: float  # 0.0 to 10.0


class CorrelationEngine:
    """
    Correlates multiple signals to identify relationships:
    - Metric spikes with Kubernetes events
    - Pod failures with resource constraints
    - Deployment changes with performance degradation
    - Cascading failures across services
    """
    
    def __init__(self, prometheus_url: str = None):
        self.prom_url = (prometheus_url or os.getenv("PROMETHEUS_URL", "http://prometheus:9090")).rstrip("/")
        self.timeout = float(os.getenv("REQUEST_TIMEOUT", "10"))
        self.k8s_tools = KubernetesTools() if KubernetesTools else None
        
        # Time window for correlation analysis
        self.correlation_window = timedelta(minutes=15)
    
    def _query_prometheus(self, query: str) -> Dict:
        """Execute a PromQL query"""
        url = f"{self.prom_url}/api/v1/query"
        try:
            with httpx.Client(timeout=self.timeout) as client:
                r = client.get(url, params={"query": query})
                r.raise_for_status()
                return r.json()
        except Exception as e:
            return {"status": "error", "error": str(e)}
    
    def _parse_event_time(self, event_time: str) -> datetime:
        """Parse Kubernetes event timestamp"""
        try:
            # Handle ISO format with 'Z' or '+00:00'
            if 'Z' in event_time:
                return datetime.fromisoformat(event_time.replace('Z', '+00:00'))
            return datetime.fromisoformat(event_time)
        except:
            return datetime.now()
    
    def correlate_restarts_with_events(self, namespace: Optional[str] = None) -> List[Correlation]:
        """Correlate pod restarts with Kubernetes events"""
        correlations = []
        
        if not self.k8s_tools:
            return correlations
        
        # Get pods with recent restarts
        query = f'increase(kube_pod_container_status_restarts_total{{namespace="{namespace}"}}[15m]) > 0' if namespace else \
                'increase(kube_pod_container_status_restarts_total[15m]) > 0'
        
        restart_result = self._query_prometheus(query)
        
        if restart_result.get("status") == "success" and restart_result.get("data", {}).get("result"):
            for item in restart_result["data"]["result"]:
                try:
                    restarts = float(item["value"][1])
                    pod = item["metric"].get("pod", "")
                    ns = item["metric"].get("namespace", "")
                    
                    if not pod or not ns:
                        continue
                    
                    # Get recent events for this pod
                    events_data = self.k8s_tools.get_events(namespace=ns, resource_name=pod)
                    
                    if events_data.get("status") == "success" and events_data.get("events"):
                        # Filter events within correlation window
                        recent_events = []
                        current_time = datetime.now()
                        
                        for event in events_data["events"][:10]:  # Check last 10 events
                            event_time = self._parse_event_time(event.get("last_seen", ""))
                            time_diff = current_time - event_time
                            
                            if time_diff <= self.correlation_window:
                                recent_events.append({
                                    "reason": event.get("reason", ""),
                                    "message": event.get("message", ""),
                                    "type": event.get("type", ""),
                                    "count": event.get("count", 0),
                                    "time": event.get("last_seen", "")
                                })
                        
                        if recent_events:
                            # Calculate confidence based on event types
                            error_events = [e for e in recent_events if e["type"] == "Warning"]
                            confidence = min(len(error_events) / 3.0, 1.0)
                            
                            correlations.append(Correlation(
                                correlation_type=CorrelationType.METRIC_TO_EVENT,
                                description=f"Pod restarts correlated with {len(recent_events)} recent events",
                                confidence=confidence,
                                timestamp=datetime.now().isoformat(),
                                primary_signal={
                                    "type": "metric",
                                    "name": "pod_restarts",
                                    "value": int(restarts),
                                    "pod": pod,
                                    "namespace": ns
                                },
                                related_signals=recent_events,
                                recommendation=self._generate_restart_recommendation(recent_events),
                                impact_score=min(restarts * 2.0, 10.0)
                            ))
                except (ValueError, KeyError):
                    continue
        
        return correlations
    
    def correlate_cpu_spikes_with_events(self, namespace: Optional[str] = None) -> List[Correlation]:
        """Correlate CPU spikes with Kubernetes events (e.g., deployments)"""
        correlations = []
        
        if not self.k8s_tools:
            return correlations
        
        # Get pods with high CPU
        query = f'sum(rate(container_cpu_usage_seconds_total{{namespace="{namespace}"}}[5m])) by (pod, namespace) * 100 > 70' if namespace else \
                'sum(rate(container_cpu_usage_seconds_total[5m])) by (pod, namespace) * 100 > 70'
        
        cpu_result = self._query_prometheus(query)
        
        if cpu_result.get("status") == "success" and cpu_result.get("data", {}).get("result"):
            for item in cpu_result["data"]["result"]:
                try:
                    cpu_value = float(item["value"][1])
                    pod = item["metric"].get("pod", "")
                    ns = item["metric"].get("namespace", "")
                    
                    if not pod or not ns:
                        continue
                    
                    # Get namespace events (deployment-related)
                    events_data = self.k8s_tools.get_events(namespace=ns)
                    
                    if events_data.get("status") == "success" and events_data.get("events"):
                        deployment_events = []
                        current_time = datetime.now()
                        
                        for event in events_data["events"][:20]:
                            event_time = self._parse_event_time(event.get("last_seen", ""))
                            time_diff = current_time - event_time
                            
                            # Look for deployment/scaling events
                            if (time_diff <= self.correlation_window and 
                                event.get("reason", "") in ["ScalingReplicaSet", "SuccessfulCreate", "Scheduled"]):
                                deployment_events.append({
                                    "reason": event.get("reason", ""),
                                    "message": event.get("message", ""),
                                    "resource": event.get("resource_name", ""),
                                    "time": event.get("last_seen", "")
                                })
                        
                        if deployment_events:
                            correlations.append(Correlation(
                                correlation_type=CorrelationType.EVENT_TO_METRIC,
                                description=f"High CPU usage correlated with recent deployment activity",
                                confidence=0.7,
                                timestamp=datetime.now().isoformat(),
                                primary_signal={
                                    "type": "metric",
                                    "name": "cpu_usage",
                                    "value": cpu_value,
                                    "pod": pod,
                                    "namespace": ns
                                },
                                related_signals=deployment_events,
                                recommendation="Recent deployment may have increased resource usage. Monitor for stabilization or consider resource adjustments.",
                                impact_score=min(cpu_value / 10.0, 10.0)
                            ))
                except (ValueError, KeyError):
                    continue
        
        return correlations
    
    def correlate_memory_with_oom_events(self, namespace: Optional[str] = None) -> List[Correlation]:
        """Correlate high memory usage with OOMKilled events"""
        correlations = []
        
        if not self.k8s_tools:
            return correlations
        
        # Get pods with high memory
        query = f'(sum(container_memory_working_set_bytes{{namespace="{namespace}"}}) by (pod, namespace) / sum(container_spec_memory_limit_bytes{{namespace="{namespace}"}}) by (pod, namespace)) * 100 > 80' if namespace else \
                '(sum(container_memory_working_set_bytes) by (pod, namespace) / sum(container_spec_memory_limit_bytes) by (pod, namespace)) * 100 > 80'
        
        memory_result = self._query_prometheus(query)
        
        if memory_result.get("status") == "success" and memory_result.get("data", {}).get("result"):
            for item in memory_result["data"]["result"]:
                try:
                    memory_pct = float(item["value"][1])
                    pod = item["metric"].get("pod", "")
                    ns = item["metric"].get("namespace", "")
                    
                    if not pod or not ns:
                        continue
                    
                    # Get events for this pod
                    events_data = self.k8s_tools.get_events(namespace=ns, resource_name=pod)
                    
                    if events_data.get("status") == "success" and events_data.get("events"):
                        oom_events = []
                        
                        for event in events_data["events"][:10]:
                            reason = event.get("reason", "")
                            if "OOM" in reason or "Killed" in reason:
                                oom_events.append({
                                    "reason": reason,
                                    "message": event.get("message", ""),
                                    "time": event.get("last_seen", ""),
                                    "count": event.get("count", 0)
                                })
                        
                        if oom_events:
                            correlations.append(Correlation(
                                correlation_type=CorrelationType.METRIC_TO_EVENT,
                                description=f"High memory usage ({memory_pct:.1f}%) with OOMKill events",
                                confidence=0.95,
                                timestamp=datetime.now().isoformat(),
                                primary_signal={
                                    "type": "metric",
                                    "name": "memory_usage_percent",
                                    "value": memory_pct,
                                    "pod": pod,
                                    "namespace": ns
                                },
                                related_signals=oom_events,
                                recommendation="Increase memory limits or investigate memory leak. Pod is at risk of OOMKill.",
                                impact_score=min(memory_pct / 10.0, 10.0)
                            ))
                except (ValueError, KeyError):
                    continue
        
        return correlations
    
    def detect_cascading_failures(self, namespace: Optional[str] = None) -> List[Correlation]:
        """Detect cascading failures across multiple pods/services"""
        correlations = []
        
        if not self.k8s_tools:
            return correlations
        
        # Get all failing pods
        failing_pods_data = self.k8s_tools.get_failing_pods(namespace)
        
        # Handle both dict and list responses
        if isinstance(failing_pods_data, dict):
            failing_pods = failing_pods_data.get("pods", [])
        elif isinstance(failing_pods_data, list):
            failing_pods = failing_pods_data
        else:
            return correlations
        
        if len(failing_pods) >= 2:
                # Group by namespace to detect namespace-wide issues
                by_namespace = defaultdict(list)
                for pod in failing_pods:
                    by_namespace[pod["namespace"]].append(pod)
                
                for ns, pods in by_namespace.items():
                    if len(pods) >= 2:
                        # Check if failures happened around the same time
                        failure_reasons = [p.get("reason", "") for p in pods]
                        common_reason = max(set(failure_reasons), key=failure_reasons.count)
                        
                        correlations.append(Correlation(
                            correlation_type=CorrelationType.CASCADING,
                            description=f"Multiple pod failures detected in namespace '{ns}'",
                            confidence=0.8,
                            timestamp=datetime.now().isoformat(),
                            primary_signal={
                                "type": "pod_failures",
                                "namespace": ns,
                                "count": len(pods),
                                "common_reason": common_reason
                            },
                            related_signals=[
                                {
                                    "pod": p["name"],
                                    "reason": p.get("reason", ""),
                                    "restarts": p.get("restarts", 0)
                                }
                                for p in pods
                            ],
                            recommendation="Multiple pods failing simultaneously suggests systemic issue. Check for resource constraints, network problems, or shared dependency failures.",
                            impact_score=min(len(pods) * 2.0, 10.0)
                        ))
        
        return correlations
    
    def _generate_restart_recommendation(self, events: List[Dict]) -> str:
        """Generate contextual recommendation based on event types"""
        reasons = [e.get("reason", "") for e in events]
        
        if any("OOM" in r or "Killed" in r for r in reasons):
            return "OOM events detected - increase memory limits or investigate memory leaks"
        elif any("Liveness" in r or "Readiness" in r for r in reasons):
            return "Health probe failures - adjust probe settings or fix application health endpoints"
        elif any("Error" in r or "Failed" in r for r in reasons):
            return "Application errors causing restarts - check logs and fix application bugs"
        else:
            return "Investigate pod logs and events for root cause of restarts"
    
    def analyze_all_correlations(self, namespace: Optional[str] = None) -> Dict[str, Any]:
        """
        Run all correlation analyses and return comprehensive report.
        
        Returns:
            Dictionary with correlations, insights, and actionable recommendations
        """
        all_correlations = {
            "restart_event_correlations": self.correlate_restarts_with_events(namespace),
            "cpu_event_correlations": self.correlate_cpu_spikes_with_events(namespace),
            "memory_oom_correlations": self.correlate_memory_with_oom_events(namespace),
            "cascading_failures": self.detect_cascading_failures(namespace),
        }
        
        # Flatten all correlations
        all_items = []
        for category, correlations in all_correlations.items():
            for corr in correlations:
                all_items.append({
                    "category": category,
                    "type": corr.correlation_type.value,
                    "description": corr.description,
                    "confidence": corr.confidence,
                    "timestamp": corr.timestamp,
                    "primary_signal": corr.primary_signal,
                    "related_signals": corr.related_signals,
                    "recommendation": corr.recommendation,
                    "impact_score": corr.impact_score
                })
        
        # Sort by impact score
        all_items.sort(key=lambda x: x["impact_score"], reverse=True)
        
        # Calculate summary stats
        high_confidence = [c for c in all_items if c["confidence"] >= 0.8]
        high_impact = [c for c in all_items if c["impact_score"] >= 7.0]
        
        result = {
            "summary": {
                "total_correlations": len(all_items),
                "high_confidence": len(high_confidence),
                "high_impact": len(high_impact),
                "timestamp": datetime.now().isoformat(),
                "namespace": namespace or "all"
            },
            "correlations": all_items,
            "top_issues": all_items[:5],  # Top 5 by impact
            "insights": self._generate_correlation_insights(all_items)
        }
        
        return result
    
    def _generate_correlation_insights(self, correlations: List[Dict]) -> List[str]:
        """Generate actionable insights from correlations"""
        insights = []
        
        if not correlations:
            insights.append("✅ No significant correlations detected - systems operating normally")
            return insights
        
        # Analyze correlation types
        by_type = defaultdict(list)
        for corr in correlations:
            by_type[corr["type"]].append(corr)
        
        if "cascading" in by_type:
            insights.append(f"🔥 Cascading failures detected - {len(by_type['cascading'])} incident(s) affecting multiple pods")
        
        if "metric_to_event" in by_type:
            insights.append(f"📊 {len(by_type['metric_to_event'])} metric anomalies correlated with Kubernetes events")
        
        if "event_to_metric" in by_type:
            insights.append(f"⚡ {len(by_type['event_to_metric'])} performance changes linked to recent deployments or scaling")
        
        # High impact correlations
        high_impact = [c for c in correlations if c["impact_score"] >= 7.0]
        if high_impact:
            insights.append(f"⚠️ {len(high_impact)} high-impact issues require immediate attention")
        
        return insights
