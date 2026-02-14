#!/usr/bin/env python3
"""
Automated Test Suite for Intelligent SRE MCP Detection Tools
Tests anomaly detection, pattern recognition, and correlation analysis
"""

import json
import time
import subprocess
import requests
from datetime import datetime
from typing import Dict, List, Any

# Configuration
API_URL = "http://localhost:30080"
NAMESPACE = "intelligent-sre"
TIMEOUT = 30

class Colors:
    HEADER = '\033[95m'
    BLUE = '\033[94m'
    GREEN = '\033[92m'
    YELLOW = '\033[93m'
    RED = '\033[91m'
    END = '\033[0m'
    BOLD = '\033[1m'

class TestRunner:
    def __init__(self):
        self.passed = 0
        self.failed = 0
        self.results = []
        
    def print_header(self, text: str):
        print(f"\n{Colors.HEADER}{Colors.BOLD}{'='*60}{Colors.END}")
        print(f"{Colors.HEADER}{Colors.BOLD}{text}{Colors.END}")
        print(f"{Colors.HEADER}{Colors.BOLD}{'='*60}{Colors.END}\n")
    
    def print_test(self, name: str):
        print(f"{Colors.BLUE}Testing: {name}{Colors.END}")
    
    def print_success(self, message: str):
        print(f"{Colors.GREEN}✓ {message}{Colors.END}")
        self.passed += 1
        
    def print_failure(self, message: str):
        print(f"{Colors.RED}✗ {message}{Colors.END}")
        self.failed += 1
        
    def print_info(self, message: str):
        print(f"{Colors.YELLOW}ℹ {message}{Colors.END}")
    
    def test_api_health(self) -> bool:
        """Test if API is responsive"""
        self.print_test("API Health Check")
        try:
            response = requests.get(f"{API_URL}/health", timeout=5)
            if response.status_code == 200:
                data = response.json()
                self.print_success(f"API is healthy: {data.get('status')}")
                return True
            else:
                self.print_failure(f"API returned status code {response.status_code}")
                return False
        except Exception as e:
            self.print_failure(f"API health check failed: {e}")
            return False
    
    def test_prometheus_connection(self) -> bool:
        """Test Prometheus connectivity"""
        self.print_test("Prometheus Connection")
        try:
            response = requests.get(
                f"{API_URL}/prom/query",
                params={"query": "up"},
                timeout=TIMEOUT
            )
            if response.status_code == 200:
                data = response.json()
                if data.get("status") == "success":
                    self.print_success("Prometheus is reachable and responding")
                    return True
                else:
                    self.print_failure(f"Prometheus query failed: {data.get('error')}")
                    return False
            else:
                self.print_failure(f"Prometheus returned status code {response.status_code}")
                return False
        except Exception as e:
            self.print_failure(f"Prometheus connection failed: {e}")
            return False
    
    def test_kubernetes_connection(self) -> bool:
        """Test Kubernetes API connectivity"""
        self.print_test("Kubernetes API Connection")
        try:
            response = requests.get(
                f"{API_URL}/k8s/pods",
                params={"namespace": NAMESPACE},
                timeout=TIMEOUT
            )
            if response.status_code == 200:
                data = response.json()
                # Handle both dict and list responses
                if isinstance(data, dict):
                    pod_count = len(data.get("pods", []))
                elif isinstance(data, list):
                    pod_count = len(data)
                else:
                    pod_count = 0
                self.print_success(f"Kubernetes API is accessible ({pod_count} pods found)")
                return True
            else:
                self.print_failure(f"K8s API returned status code {response.status_code}")
                return False
        except Exception as e:
            self.print_failure(f"Kubernetes connection failed: {e}")
            return False
    
    def test_anomaly_detection(self) -> Dict[str, Any]:
        """Test anomaly detection endpoint"""
        self.print_test("Anomaly Detection")
        try:
            response = requests.get(
                f"{API_URL}/detection/anomalies",
                params={"namespace": NAMESPACE},
                timeout=TIMEOUT
            )
            if response.status_code == 200:
                data = response.json()
                total = data.get("total_anomalies", 0)
                cpu = len(data.get("cpu_anomalies", []))
                memory = len(data.get("memory_anomalies", []))
                restarts = len(data.get("restart_anomalies", []))
                pending = len(data.get("pending_pod_anomalies", []))
                
                self.print_success(f"Anomaly detection working: {total} total anomalies")
                self.print_info(f"  CPU: {cpu}, Memory: {memory}, Restarts: {restarts}, Pending: {pending}")
                return data
            else:
                self.print_failure(f"Anomaly detection returned status code {response.status_code}")
                return {}
        except Exception as e:
            self.print_failure(f"Anomaly detection failed: {e}")
            return {}
    
    def test_health_score(self) -> float:
        """Test health score calculation"""
        self.print_test("Health Score Calculation")
        try:
            response = requests.get(
                f"{API_URL}/detection/health-score",
                params={"namespace": NAMESPACE},
                timeout=TIMEOUT
            )
            if response.status_code == 200:
                data = response.json()
                score = data.get("health_score", 0)
                status = data.get("status", "unknown")
                emoji = data.get("status_emoji", "")
                
                self.print_success(f"Health score: {score}/100 - {status} {emoji}")
                
                if score >= 90:
                    self.print_info("  System is HEALTHY")
                elif score >= 70:
                    self.print_info("  System is DEGRADED")
                elif score >= 50:
                    self.print_info("  System is UNHEALTHY")
                else:
                    self.print_info("  System is CRITICAL")
                
                return score
            else:
                self.print_failure(f"Health score returned status code {response.status_code}")
                return 0.0
        except Exception as e:
            self.print_failure(f"Health score calculation failed: {e}")
            return 0.0
    
    def test_pattern_recognition(self) -> Dict[str, Any]:
        """Test pattern recognition"""
        self.print_test("Pattern Recognition")
        try:
            response = requests.get(
                f"{API_URL}/detection/patterns",
                params={"namespace": NAMESPACE},
                timeout=TIMEOUT
            )
            if response.status_code == 200:
                data = response.json()
                total = data.get("total_patterns", 0)
                recurring = len(data.get("recurring_failures", []))
                cyclic = len(data.get("cyclic_spikes", []))
                exhaustion = len(data.get("resource_exhaustion", []))
                cascading = len(data.get("cascading_failures", []))
                
                self.print_success(f"Pattern recognition working: {total} patterns detected")
                self.print_info(f"  Recurring: {recurring}, Cyclic: {cyclic}, Exhaustion: {exhaustion}, Cascading: {cascading}")
                return data
            else:
                self.print_failure(f"Pattern recognition returned status code {response.status_code}")
                return {}
        except Exception as e:
            self.print_failure(f"Pattern recognition failed: {e}")
            return {}
    
    def test_correlation_analysis(self) -> Dict[str, Any]:
        """Test correlation analysis"""
        self.print_test("Correlation Analysis")
        try:
            response = requests.get(
                f"{API_URL}/detection/correlations",
                params={"namespace": NAMESPACE},
                timeout=TIMEOUT
            )
            if response.status_code == 200:
                data = response.json()
                total = data.get("total_correlations", 0)
                restart_event = len(data.get("restart_event_correlations", []))
                cpu_event = len(data.get("cpu_event_correlations", []))
                memory_oom = len(data.get("memory_oom_correlations", []))
                
                self.print_success(f"Correlation analysis working: {total} correlations found")
                self.print_info(f"  Restart-Event: {restart_event}, CPU-Event: {cpu_event}, Memory-OOM: {memory_oom}")
                return data
            else:
                self.print_failure(f"Correlation analysis returned status code {response.status_code}")
                return {}
        except Exception as e:
            self.print_failure(f"Correlation analysis failed: {e}")
            return {}
    
    def test_comprehensive_analysis(self) -> Dict[str, Any]:
        """Test comprehensive analysis endpoint"""
        self.print_test("Comprehensive Analysis")
        try:
            response = requests.get(
                f"{API_URL}/detection/comprehensive",
                params={"namespace": NAMESPACE},
                timeout=TIMEOUT * 2  # Longer timeout for comprehensive
            )
            if response.status_code == 200:
                data = response.json()
                health = data.get("health_score", {})
                anomalies = data.get("anomalies", {})
                patterns = data.get("patterns", {})
                correlations = data.get("correlations", {})
                
                self.print_success("Comprehensive analysis completed successfully")
                self.print_info(f"  Health Score: {health.get('health_score', 0)}/100")
                self.print_info(f"  Total Anomalies: {anomalies.get('total_anomalies', 0)}")
                self.print_info(f"  Total Patterns: {patterns.get('total_patterns', 0)}")
                self.print_info(f"  Total Correlations: {correlations.get('total_correlations', 0)}")
                return data
            else:
                self.print_failure(f"Comprehensive analysis returned status code {response.status_code}")
                return {}
        except Exception as e:
            self.print_failure(f"Comprehensive analysis failed: {e}")
            return {}
    
    def test_metric_spike_detection(self) -> Dict[str, Any]:
        """Test custom metric spike detection"""
        self.print_test("Metric Spike Detection")
        try:
            # Test CPU spike detection
            query = "sum(rate(container_cpu_usage_seconds_total[5m])) by (pod) * 100"
            response = requests.get(
                f"{API_URL}/detection/spike",
                params={
                    "query": query,
                    "duration": "1h",
                    "spike_multiplier": 2.0
                },
                timeout=TIMEOUT
            )
            if response.status_code == 200:
                data = response.json()
                spike_detected = data.get("spike_detected", False)
                
                if spike_detected:
                    self.print_success("Spike detection working - spike found")
                else:
                    self.print_success("Spike detection working - no spikes (normal)")
                
                return data
            else:
                self.print_failure(f"Spike detection returned status code {response.status_code}")
                return {}
        except Exception as e:
            self.print_failure(f"Spike detection failed: {e}")
            return {}
    
    def test_prometheus_targets(self) -> Dict[str, Any]:
        """Test Prometheus targets health"""
        self.print_test("Prometheus Targets Health")
        try:
            response = requests.get(
                f"{API_URL}/prom/targets",
                timeout=TIMEOUT
            )
            if response.status_code == 200:
                data = response.json()
                targets = data.get("data", {}).get("activeTargets", [])
                healthy = sum(1 for t in targets if t.get("health") == "up")
                total = len(targets)
                
                self.print_success(f"Targets check complete: {healthy}/{total} healthy")
                
                for target in targets[:5]:  # Show first 5
                    job = target.get("labels", {}).get("job", "unknown")
                    health = target.get("health", "unknown")
                    emoji = "✓" if health == "up" else "✗"
                    self.print_info(f"  {emoji} {job}: {health}")
                
                return data
            else:
                self.print_failure(f"Targets check returned status code {response.status_code}")
                return {}
        except Exception as e:
            self.print_failure(f"Targets check failed: {e}")
            return {}
    
    def create_test_pod(self, pod_name: str, pod_spec: str) -> bool:
        """Create a test pod using kubectl"""
        self.print_info(f"Creating test pod: {pod_name}")
        try:
            result = subprocess.run(
                ["kubectl", "apply", "-f", "-"],
                input=pod_spec.encode(),
                capture_output=True,
                timeout=30
            )
            if result.returncode == 0:
                self.print_success(f"Test pod {pod_name} created")
                return True
            else:
                self.print_failure(f"Failed to create test pod: {result.stderr.decode()}")
                return False
        except Exception as e:
            self.print_failure(f"Failed to create test pod: {e}")
            return False
    
    def delete_test_pod(self, pod_name: str) -> bool:
        """Delete a test pod"""
        self.print_info(f"Deleting test pod: {pod_name}")
        try:
            result = subprocess.run(
                ["kubectl", "delete", "pod", pod_name, "-n", NAMESPACE, "--force", "--grace-period=0"],
                capture_output=True,
                timeout=30
            )
            if result.returncode == 0:
                self.print_success(f"Test pod {pod_name} deleted")
                return True
            else:
                self.print_info(f"Pod deletion status: {result.stderr.decode()}")
                return True  # Don't fail if pod doesn't exist
        except Exception as e:
            self.print_failure(f"Failed to delete test pod: {e}")
            return False
    
    def run_all_tests(self):
        """Run all tests"""
        self.print_header("Intelligent SRE MCP - Test Suite")
        
        print(f"{Colors.BOLD}Starting test run at {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}{Colors.END}\n")
        
        # Basic connectivity tests
        self.print_header("Phase 1: Basic Connectivity")
        if not self.test_api_health():
            print(f"\n{Colors.RED}API is not healthy. Stopping tests.{Colors.END}\n")
            return
        
        self.test_prometheus_connection()
        self.test_kubernetes_connection()
        self.test_prometheus_targets()
        
        # Detection tests
        self.print_header("Phase 2: Detection Engines")
        anomalies = self.test_anomaly_detection()
        health_score = self.test_health_score()
        patterns = self.test_pattern_recognition()
        correlations = self.test_correlation_analysis()
        
        # Advanced tests
        self.print_header("Phase 3: Advanced Features")
        comprehensive = self.test_comprehensive_analysis()
        spike_data = self.test_metric_spike_detection()
        
        # Summary
        self.print_header("Test Summary")
        total = self.passed + self.failed
        pass_rate = (self.passed / total * 100) if total > 0 else 0
        
        print(f"{Colors.BOLD}Results:{Colors.END}")
        print(f"  {Colors.GREEN}Passed: {self.passed}{Colors.END}")
        print(f"  {Colors.RED}Failed: {self.failed}{Colors.END}")
        print(f"  {Colors.BLUE}Total: {total}{Colors.END}")
        print(f"  {Colors.BOLD}Pass Rate: {pass_rate:.1f}%{Colors.END}\n")
        
        if self.failed == 0:
            print(f"{Colors.GREEN}{Colors.BOLD}✓ All tests passed!{Colors.END}\n")
        else:
            print(f"{Colors.YELLOW}{Colors.BOLD}⚠ Some tests failed. Please review the output above.{Colors.END}\n")
        
        return self.failed == 0

if __name__ == "__main__":
    runner = TestRunner()
    success = runner.run_all_tests()
    exit(0 if success else 1)
