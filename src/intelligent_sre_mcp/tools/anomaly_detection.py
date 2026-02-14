"""
Anomaly Detection Module
Implements statistical analysis and machine learning techniques for detecting anomalies
in metrics and Kubernetes behavior.
"""

import os
import httpx
from typing import Dict, List, Optional, Tuple, Any
from datetime import datetime, timedelta
import statistics
from dataclasses import dataclass
from enum import Enum


class AnomalyLevel(str, Enum):
    """Severity levels for detected anomalies"""
    CRITICAL = "critical"
    WARNING = "warning"
    INFO = "info"


@dataclass
class Anomaly:
    """Represents a detected anomaly"""
    metric_name: str
    current_value: float
    expected_range: Tuple[float, float]
    deviation: float
    level: AnomalyLevel
    timestamp: str
    description: str
    labels: Dict[str, str] = None


class AnomalyDetector:
    """
    Detects anomalies using statistical methods:
    - Z-score analysis for outlier detection
    - Moving average deviation
    - Threshold-based rules
    - Rate of change analysis
    """
    
    def __init__(self, prometheus_url: str = None):
        self.prom_url = (prometheus_url or os.getenv("PROMETHEUS_URL", "http://prometheus:9090")).rstrip("/")
        self.timeout = float(os.getenv("REQUEST_TIMEOUT", "10"))
        
        # Thresholds for anomaly detection
        self.z_score_threshold = 3.0  # Standard deviations from mean
        self.high_cpu_threshold = 80.0  # Percentage
        self.high_memory_threshold = 85.0  # Percentage
        self.pod_restart_threshold = 5  # Number of restarts
        
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
    
    def _query_prometheus_range(self, query: str, duration: str = "1h") -> Dict:
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
    
    def _calculate_z_score(self, value: float, values: List[float]) -> float:
        """Calculate Z-score for a value"""
        if len(values) < 2:
            return 0.0
        
        mean = statistics.mean(values)
        try:
            stdev = statistics.stdev(values)
            if stdev == 0:
                return 0.0
            return abs((value - mean) / stdev)
        except statistics.StatisticsError:
            return 0.0
    
    def detect_cpu_anomalies(self, namespace: Optional[str] = None) -> List[Anomaly]:
        """Detect CPU usage anomalies"""
        anomalies = []
        
        # Query for high CPU usage
        if namespace:
            query = f'sum(rate(container_cpu_usage_seconds_total{{namespace="{namespace}"}}[5m])) by (pod) * 100'
        else:
            query = 'sum(rate(container_cpu_usage_seconds_total[5m])) by (pod, namespace) * 100'
        
        result = self._query_prometheus(query)
        
        if result.get("status") == "success" and result.get("data", {}).get("result"):
            for item in result["data"]["result"]:
                try:
                    value = float(item["value"][1])
                    pod = item["metric"].get("pod", "unknown")
                    ns = item["metric"].get("namespace", "unknown")
                    
                    if value > self.high_cpu_threshold:
                        anomalies.append(Anomaly(
                            metric_name="cpu_usage",
                            current_value=value,
                            expected_range=(0.0, self.high_cpu_threshold),
                            deviation=value - self.high_cpu_threshold,
                            level=AnomalyLevel.CRITICAL if value > 95 else AnomalyLevel.WARNING,
                            timestamp=datetime.now().isoformat(),
                            description=f"High CPU usage detected: {value:.2f}%",
                            labels={"pod": pod, "namespace": ns}
                        ))
                except (ValueError, KeyError):
                    continue
        
        return anomalies
    
    def detect_memory_anomalies(self, namespace: Optional[str] = None) -> List[Anomaly]:
        """Detect memory usage anomalies"""
        anomalies = []
        
        # Query for high memory usage
        if namespace:
            query = f'(sum(container_memory_working_set_bytes{{namespace="{namespace}"}}) by (pod) / sum(container_spec_memory_limit_bytes{{namespace="{namespace}"}}) by (pod)) * 100'
        else:
            query = '(sum(container_memory_working_set_bytes) by (pod, namespace) / sum(container_spec_memory_limit_bytes) by (pod, namespace)) * 100'
        
        result = self._query_prometheus(query)
        
        if result.get("status") == "success" and result.get("data", {}).get("result"):
            for item in result["data"]["result"]:
                try:
                    value = float(item["value"][1])
                    pod = item["metric"].get("pod", "unknown")
                    ns = item["metric"].get("namespace", "unknown")
                    
                    if value > self.high_memory_threshold:
                        anomalies.append(Anomaly(
                            metric_name="memory_usage",
                            current_value=value,
                            expected_range=(0.0, self.high_memory_threshold),
                            deviation=value - self.high_memory_threshold,
                            level=AnomalyLevel.CRITICAL if value > 95 else AnomalyLevel.WARNING,
                            timestamp=datetime.now().isoformat(),
                            description=f"High memory usage detected: {value:.2f}%",
                            labels={"pod": pod, "namespace": ns}
                        ))
                except (ValueError, KeyError):
                    continue
        
        return anomalies
    
    def detect_pod_restart_anomalies(self, namespace: Optional[str] = None) -> List[Anomaly]:
        """Detect pods with excessive restarts"""
        anomalies = []
        
        # Query for pod restarts
        if namespace:
            query = f'kube_pod_container_status_restarts_total{{namespace="{namespace}"}}'
        else:
            query = 'kube_pod_container_status_restarts_total'
        
        result = self._query_prometheus(query)
        
        if result.get("status") == "success" and result.get("data", {}).get("result"):
            for item in result["data"]["result"]:
                try:
                    value = float(item["value"][1])
                    pod = item["metric"].get("pod", "unknown")
                    ns = item["metric"].get("namespace", "unknown")
                    container = item["metric"].get("container", "unknown")
                    
                    if value >= self.pod_restart_threshold:
                        anomalies.append(Anomaly(
                            metric_name="pod_restarts",
                            current_value=value,
                            expected_range=(0.0, float(self.pod_restart_threshold)),
                            deviation=value - self.pod_restart_threshold,
                            level=AnomalyLevel.CRITICAL if value > 10 else AnomalyLevel.WARNING,
                            timestamp=datetime.now().isoformat(),
                            description=f"Pod restarting frequently: {int(value)} restarts",
                            labels={"pod": pod, "namespace": ns, "container": container}
                        ))
                except (ValueError, KeyError):
                    continue
        
        return anomalies
    
    def detect_pod_pending_anomalies(self) -> List[Anomaly]:
        """Detect pods stuck in pending state"""
        anomalies = []
        
        query = 'kube_pod_status_phase{phase="Pending"}'
        result = self._query_prometheus(query)
        
        if result.get("status") == "success" and result.get("data", {}).get("result"):
            for item in result["data"]["result"]:
                try:
                    pod = item["metric"].get("pod", "unknown")
                    ns = item["metric"].get("namespace", "unknown")
                    
                    anomalies.append(Anomaly(
                        metric_name="pod_pending",
                        current_value=1.0,
                        expected_range=(0.0, 0.0),
                        deviation=1.0,
                        level=AnomalyLevel.WARNING,
                        timestamp=datetime.now().isoformat(),
                        description=f"Pod stuck in Pending state",
                        labels={"pod": pod, "namespace": ns}
                    ))
                except (ValueError, KeyError):
                    continue
        
        return anomalies
    
    def detect_metric_spikes(self, metric_query: str, duration: str = "1h", 
                            spike_multiplier: float = 2.0) -> List[Anomaly]:
        """
        Detect sudden spikes in any metric by comparing current value to historical average.
        
        Args:
            metric_query: PromQL query for the metric
            duration: Historical period to analyze (e.g., '1h', '6h', '1d')
            spike_multiplier: How many times higher than average to trigger anomaly
        """
        anomalies = []
        
        # Get historical data
        range_result = self._query_prometheus_range(metric_query, duration)
        current_result = self._query_prometheus(metric_query)
        
        if (range_result.get("status") == "success" and 
            current_result.get("status") == "success"):
            
            range_data = range_result.get("data", {}).get("result", [])
            current_data = current_result.get("data", {}).get("result", [])
            
            # Match current values with historical data
            for curr_item in current_data:
                metric_labels = curr_item.get("metric", {})
                
                # Find matching historical series
                for hist_item in range_data:
                    if hist_item.get("metric") == metric_labels:
                        try:
                            current_value = float(curr_item["value"][1])
                            historical_values = [float(v[1]) for v in hist_item.get("values", [])]
                            
                            if len(historical_values) < 2:
                                continue
                            
                            avg_value = statistics.mean(historical_values)
                            
                            # Detect spike
                            if avg_value > 0 and current_value > avg_value * spike_multiplier:
                                z_score = self._calculate_z_score(current_value, historical_values)
                                
                                anomalies.append(Anomaly(
                                    metric_name=metric_query,
                                    current_value=current_value,
                                    expected_range=(0.0, avg_value * spike_multiplier),
                                    deviation=current_value - avg_value,
                                    level=AnomalyLevel.CRITICAL if z_score > 5 else AnomalyLevel.WARNING,
                                    timestamp=datetime.now().isoformat(),
                                    description=f"Metric spike detected: {current_value:.2f} (avg: {avg_value:.2f}, z-score: {z_score:.2f})",
                                    labels=metric_labels
                                ))
                        except (ValueError, KeyError, statistics.StatisticsError):
                            continue
        
        return anomalies
    
    def detect_all_anomalies(self, namespace: Optional[str] = None) -> Dict[str, Any]:
        """
        Run all anomaly detection checks and return comprehensive report.
        
        Returns:
            Dictionary with anomaly counts, details, and summary
        """
        all_anomalies = {
            "cpu_anomalies": self.detect_cpu_anomalies(namespace),
            "memory_anomalies": self.detect_memory_anomalies(namespace),
            "restart_anomalies": self.detect_pod_restart_anomalies(namespace),
            "pending_pod_anomalies": self.detect_pod_pending_anomalies(),
        }
        
        # Count by severity
        total_critical = sum(
            len([a for a in anomalies if a.level == AnomalyLevel.CRITICAL])
            for anomalies in all_anomalies.values()
        )
        total_warning = sum(
            len([a for a in anomalies if a.level == AnomalyLevel.WARNING])
            for anomalies in all_anomalies.values()
        )
        
        total_anomalies = total_critical + total_warning
        
        # Convert anomalies to dict format
        result = {
            "summary": {
                "total_anomalies": total_anomalies,
                "critical": total_critical,
                "warning": total_warning,
                "timestamp": datetime.now().isoformat(),
                "namespace": namespace or "all"
            },
            "anomalies": {
                category: [
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
                for category, anomalies in all_anomalies.items()
            }
        }
        
        return result
    
    def get_health_score(self, namespace: Optional[str] = None) -> Dict[str, Any]:
        """
        Calculate overall health score (0-100) based on detected anomalies.
        
        Returns:
            Dictionary with health score, status, and recommendations
        """
        anomaly_report = self.detect_all_anomalies(namespace)
        
        # Calculate score (start at 100, deduct points for anomalies)
        score = 100.0
        score -= anomaly_report["summary"]["critical"] * 15  # -15 per critical
        score -= anomaly_report["summary"]["warning"] * 5    # -5 per warning
        score = max(0.0, score)  # Don't go below 0
        
        # Determine status
        if score >= 90:
            status = "healthy"
            status_emoji = "✅"
        elif score >= 70:
            status = "degraded"
            status_emoji = "⚠️"
        elif score >= 50:
            status = "unhealthy"
            status_emoji = "❌"
        else:
            status = "critical"
            status_emoji = "🔥"
        
        # Generate recommendations
        recommendations = []
        for category, anomalies in anomaly_report["anomalies"].items():
            for anomaly in anomalies[:3]:  # Top 3 per category
                recommendations.append({
                    "priority": anomaly["level"],
                    "message": anomaly["description"],
                    "resource": anomaly["labels"]
                })
        
        return {
            "health_score": score,
            "status": status,
            "status_emoji": status_emoji,
            "namespace": namespace or "all",
            "timestamp": datetime.now().isoformat(),
            "anomaly_summary": anomaly_report["summary"],
            "recommendations": recommendations[:10]  # Top 10 recommendations
        }
