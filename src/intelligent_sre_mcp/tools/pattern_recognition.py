"""
Pattern Recognition Module
Identifies recurring issues, patterns, and trends in metrics and Kubernetes events.
"""

import os
import httpx
from typing import Dict, List, Optional, Any, Tuple
from datetime import datetime, timedelta
from collections import defaultdict, Counter
from dataclasses import dataclass
from enum import Enum


class PatternType(str, Enum):
    """Types of patterns that can be detected"""
    RECURRING_FAILURE = "recurring_failure"
    CYCLIC_SPIKE = "cyclic_spike"
    CASCADING_FAILURE = "cascading_failure"
    RESOURCE_EXHAUSTION = "resource_exhaustion"
    DEPLOYMENT_ISSUE = "deployment_issue"


@dataclass
class Pattern:
    """Represents a detected pattern"""
    pattern_type: PatternType
    description: str
    occurrences: int
    affected_resources: List[Dict[str, str]]
    first_seen: str
    last_seen: str
    confidence: float  # 0.0 to 1.0
    recommendation: str
    details: Dict[str, Any] = None


class PatternRecognizer:
    """
    Recognizes patterns in metrics and events:
    - Recurring pod failures
    - Cyclic resource spikes
    - Cascading failures across services
    - Resource exhaustion trends
    """
    
    def __init__(self, prometheus_url: str = None):
        self.prom_url = (prometheus_url or os.getenv("PROMETHEUS_URL", "http://prometheus:9090")).rstrip("/")
        self.timeout = float(os.getenv("REQUEST_TIMEOUT", "10"))
        
        # Pattern detection thresholds
        self.recurring_failure_threshold = 3  # Minimum occurrences
        self.time_window = "6h"  # Analysis window
        
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
    
    def _query_prometheus_range(self, query: str, duration: str = "6h") -> Dict:
        """Execute a PromQL range query"""
        url = f"{self.prom_url}/api/v1/query_range"
        end_time = datetime.now()
        start_time = end_time - self._parse_duration(duration)
        
        try:
            with httpx.Client(timeout=self.timeout) as client:
                r = client.get(url, params={
                    "query": query,
                    "start": start_time.timestamp(),
                    "end": end_time.timestamp(),
                    "step": "60s"
                })
                r.raise_for_status()
                return r.json()
        except Exception as e:
            return {"status": "error", "error": str(e)}
    
    def _parse_duration(self, duration: str) -> timedelta:
        """Parse duration string like '1h', '30m', '1d'"""
        unit = duration[-1]
        value = int(duration[:-1])
        
        if unit == 'h':
            return timedelta(hours=value)
        elif unit == 'm':
            return timedelta(minutes=value)
        elif unit == 'd':
            return timedelta(days=value)
        else:
            return timedelta(hours=1)
    
    def detect_recurring_pod_failures(self, namespace: Optional[str] = None) -> List[Pattern]:
        """Detect pods that are repeatedly failing"""
        patterns = []
        
        # Query for pod restart count over time
        if namespace:
            query = f'changes(kube_pod_container_status_restarts_total{{namespace="{namespace}"}}[{self.time_window}])'
        else:
            query = f'changes(kube_pod_container_status_restarts_total[{self.time_window}])'
        
        result = self._query_prometheus(query)
        
        if result.get("status") == "success" and result.get("data", {}).get("result"):
            for item in result["data"]["result"]:
                try:
                    restarts = float(item["value"][1])
                    
                    if restarts >= self.recurring_failure_threshold:
                        pod = item["metric"].get("pod", "unknown")
                        ns = item["metric"].get("namespace", "unknown")
                        container = item["metric"].get("container", "unknown")
                        
                        # Calculate confidence based on restart count
                        confidence = min(restarts / 10.0, 1.0)
                        
                        patterns.append(Pattern(
                            pattern_type=PatternType.RECURRING_FAILURE,
                            description=f"Pod '{pod}' is repeatedly failing and restarting",
                            occurrences=int(restarts),
                            affected_resources=[{
                                "pod": pod,
                                "namespace": ns,
                                "container": container
                            }],
                            first_seen=(datetime.now() - self._parse_duration(self.time_window)).isoformat(),
                            last_seen=datetime.now().isoformat(),
                            confidence=confidence,
                            recommendation=f"Investigate pod logs and check for resource limits, configuration issues, or application errors",
                            details={"restarts_in_window": int(restarts)}
                        ))
                except (ValueError, KeyError):
                    continue
        
        return patterns
    
    def detect_cyclic_cpu_spikes(self, namespace: Optional[str] = None) -> List[Pattern]:
        """Detect cyclic patterns in CPU usage"""
        patterns = []
        
        # Query CPU usage over time
        if namespace:
            query = f'sum(rate(container_cpu_usage_seconds_total{{namespace="{namespace}"}}[5m])) by (pod) * 100'
        else:
            query = 'sum(rate(container_cpu_usage_seconds_total[5m])) by (pod, namespace) * 100'
        
        result = self._query_prometheus_range(query, self.time_window)
        
        if result.get("status") == "success" and result.get("data", {}).get("result"):
            for item in result["data"]["result"]:
                try:
                    values = [float(v[1]) for v in item.get("values", [])]
                    
                    if len(values) < 10:
                        continue
                    
                    # Simple spike detection: count how many times value crosses threshold
                    threshold = 70.0
                    spikes = sum(1 for i in range(1, len(values)) 
                                if values[i] > threshold and values[i-1] <= threshold)
                    
                    if spikes >= 3:  # At least 3 spikes
                        pod = item["metric"].get("pod", "unknown")
                        ns = item["metric"].get("namespace", "unknown")
                        
                        patterns.append(Pattern(
                            pattern_type=PatternType.CYCLIC_SPIKE,
                            description=f"Cyclic CPU spikes detected in pod '{pod}'",
                            occurrences=spikes,
                            affected_resources=[{"pod": pod, "namespace": ns}],
                            first_seen=(datetime.now() - self._parse_duration(self.time_window)).isoformat(),
                            last_seen=datetime.now().isoformat(),
                            confidence=min(spikes / 10.0, 1.0),
                            recommendation="Investigate scheduled jobs, cron tasks, or periodic workloads causing CPU spikes",
                            details={"spike_count": spikes, "threshold": threshold}
                        ))
                except (ValueError, KeyError):
                    continue
        
        return patterns
    
    def detect_resource_exhaustion_trend(self, namespace: Optional[str] = None) -> List[Pattern]:
        """Detect gradual resource exhaustion (memory leak patterns)"""
        patterns = []
        
        # Query memory usage trend
        if namespace:
            query = f'sum(container_memory_working_set_bytes{{namespace="{namespace}"}}) by (pod)'
        else:
            query = 'sum(container_memory_working_set_bytes) by (pod, namespace)'
        
        result = self._query_prometheus_range(query, self.time_window)
        
        if result.get("status") == "success" and result.get("data", {}).get("result"):
            for item in result["data"]["result"]:
                try:
                    values = [float(v[1]) for v in item.get("values", [])]
                    
                    if len(values) < 20:
                        continue
                    
                    # Check for upward trend (simple: compare first quarter vs last quarter)
                    quarter_size = len(values) // 4
                    first_quarter_avg = sum(values[:quarter_size]) / quarter_size
                    last_quarter_avg = sum(values[-quarter_size:]) / quarter_size
                    
                    # If memory increased by more than 50%
                    if first_quarter_avg > 0 and last_quarter_avg > first_quarter_avg * 1.5:
                        pod = item["metric"].get("pod", "unknown")
                        ns = item["metric"].get("namespace", "unknown")
                        
                        increase_pct = ((last_quarter_avg - first_quarter_avg) / first_quarter_avg) * 100
                        
                        patterns.append(Pattern(
                            pattern_type=PatternType.RESOURCE_EXHAUSTION,
                            description=f"Memory exhaustion trend detected in pod '{pod}' ({increase_pct:.1f}% increase)",
                            occurrences=1,
                            affected_resources=[{"pod": pod, "namespace": ns}],
                            first_seen=(datetime.now() - self._parse_duration(self.time_window)).isoformat(),
                            last_seen=datetime.now().isoformat(),
                            confidence=min(increase_pct / 200.0, 1.0),
                            recommendation="Possible memory leak - review application code, check for resource cleanup, consider heap dump analysis",
                            details={
                                "initial_avg_bytes": first_quarter_avg,
                                "current_avg_bytes": last_quarter_avg,
                                "increase_percentage": increase_pct
                            }
                        ))
                except (ValueError, KeyError, ZeroDivisionError):
                    continue
        
        return patterns
    
    def detect_cascading_failures(self, namespace: Optional[str] = None) -> List[Pattern]:
        """Detect cascading failures across multiple pods/services"""
        patterns = []
        
        # Query for pod failures over time
        if namespace:
            query = f'sum(kube_pod_status_phase{{phase="Failed", namespace="{namespace}"}}) by (namespace)'
        else:
            query = 'sum(kube_pod_status_phase{phase="Failed"}) by (namespace)'
        
        result = self._query_prometheus_range(query, "30m")
        
        if result.get("status") == "success" and result.get("data", {}).get("result"):
            for item in result["data"]["result"]:
                try:
                    values = [float(v[1]) for v in item.get("values", [])]
                    
                    # Look for rapid increase in failures
                    if len(values) >= 5:
                        # Check if failures increased by 3+ in short time
                        if values[-1] - values[0] >= 3:
                            ns = item["metric"].get("namespace", "unknown")
                            
                            patterns.append(Pattern(
                                pattern_type=PatternType.CASCADING_FAILURE,
                                description=f"Cascading failures detected in namespace '{ns}'",
                                occurrences=int(values[-1] - values[0]),
                                affected_resources=[{"namespace": ns}],
                                first_seen=(datetime.now() - timedelta(minutes=30)).isoformat(),
                                last_seen=datetime.now().isoformat(),
                                confidence=0.8,
                                recommendation="Multiple pods failing simultaneously - check for shared dependencies, network issues, or resource constraints",
                                details={"failed_pods_count": int(values[-1])}
                            ))
                except (ValueError, KeyError):
                    continue
        
        return patterns
    
    def detect_deployment_rollout_issues(self, namespace: Optional[str] = None) -> List[Pattern]:
        """Detect problematic deployment rollouts"""
        patterns = []
        
        # Query for deployments with unavailable replicas
        if namespace:
            query = f'kube_deployment_status_replicas_unavailable{{namespace="{namespace}"}} > 0'
        else:
            query = 'kube_deployment_status_replicas_unavailable > 0'
        
        result = self._query_prometheus(query)
        
        if result.get("status") == "success" and result.get("data", {}).get("result"):
            for item in result["data"]["result"]:
                try:
                    unavailable = float(item["value"][1])
                    deployment = item["metric"].get("deployment", "unknown")
                    ns = item["metric"].get("namespace", "unknown")
                    
                    patterns.append(Pattern(
                        pattern_type=PatternType.DEPLOYMENT_ISSUE,
                        description=f"Deployment '{deployment}' has unavailable replicas",
                        occurrences=int(unavailable),
                        affected_resources=[{
                            "deployment": deployment,
                            "namespace": ns
                        }],
                        first_seen=datetime.now().isoformat(),
                        last_seen=datetime.now().isoformat(),
                        confidence=0.9,
                        recommendation="Check deployment status with 'kubectl rollout status', review recent changes, consider rollback if needed",
                        details={"unavailable_replicas": int(unavailable)}
                    ))
                except (ValueError, KeyError):
                    continue
        
        return patterns
    
    def analyze_all_patterns(self, namespace: Optional[str] = None) -> Dict[str, Any]:
        """
        Run all pattern recognition checks and return comprehensive report.
        
        Returns:
            Dictionary with detected patterns, summary, and insights
        """
        all_patterns = {
            "recurring_failures": self.detect_recurring_pod_failures(namespace),
            "cyclic_spikes": self.detect_cyclic_cpu_spikes(namespace),
            "resource_exhaustion": self.detect_resource_exhaustion_trend(namespace),
            "cascading_failures": self.detect_cascading_failures(namespace),
            "deployment_issues": self.detect_deployment_rollout_issues(namespace),
        }
        
        # Count patterns by type
        total_patterns = sum(len(patterns) for patterns in all_patterns.values())
        
        # Group by confidence level
        high_confidence = sum(
            len([p for p in patterns if p.confidence >= 0.8])
            for patterns in all_patterns.values()
        )
        
        # Convert patterns to dict format
        result = {
            "summary": {
                "total_patterns": total_patterns,
                "high_confidence_patterns": high_confidence,
                "timestamp": datetime.now().isoformat(),
                "analysis_window": self.time_window,
                "namespace": namespace or "all"
            },
            "patterns": {
                category: [
                    {
                        "type": p.pattern_type.value,
                        "description": p.description,
                        "occurrences": p.occurrences,
                        "affected_resources": p.affected_resources,
                        "first_seen": p.first_seen,
                        "last_seen": p.last_seen,
                        "confidence": p.confidence,
                        "recommendation": p.recommendation,
                        "details": p.details or {}
                    }
                    for p in patterns
                ]
                for category, patterns in all_patterns.items()
            },
            "insights": self._generate_insights(all_patterns)
        }
        
        return result
    
    def _generate_insights(self, all_patterns: Dict[str, List[Pattern]]) -> List[str]:
        """Generate human-readable insights from detected patterns"""
        insights = []
        
        # Count total issues
        total = sum(len(patterns) for patterns in all_patterns.values())
        
        if total == 0:
            insights.append("✅ No problematic patterns detected in the analysis window")
            return insights
        
        # Analyze recurring failures
        recurring = all_patterns.get("recurring_failures", [])
        if recurring:
            insights.append(f"⚠️ Found {len(recurring)} pods with recurring failures - these need immediate attention")
        
        # Analyze resource exhaustion
        exhaustion = all_patterns.get("resource_exhaustion", [])
        if exhaustion:
            insights.append(f"📈 Detected {len(exhaustion)} potential memory leaks or resource exhaustion trends")
        
        # Analyze cascading failures
        cascading = all_patterns.get("cascading_failures", [])
        if cascading:
            insights.append(f"🔥 {len(cascading)} cascading failure patterns detected - possible systemic issue")
        
        # Analyze cyclic patterns
        cyclic = all_patterns.get("cyclic_spikes", [])
        if cyclic:
            insights.append(f"🔄 {len(cyclic)} cyclic patterns found - likely scheduled workloads or periodic processes")
        
        # Deployment issues
        deployment = all_patterns.get("deployment_issues", [])
        if deployment:
            insights.append(f"🚀 {len(deployment)} deployment rollout issues - check recent changes")
        
        return insights
