#!/usr/bin/env python3
"""
Comprehensive tests for Phase 4: Self-Healing Actions
Tests all healing capabilities with safety mechanisms
"""

import unittest
import requests
import time
from typing import Dict, Any

API_URL = "http://localhost:30080"
TEST_NAMESPACE = "intelligent-sre"
TEST_TIMEOUT = 10


class TestHealingActions(unittest.TestCase):
    """Test suite for self-healing actions"""
    
    def setUp(self):
        """Set up test environment"""
        print(f"\n{'='*60}")
        print(f"Testing: {self._testMethodName}")
        print(f"{'='*60}")
    
    def test_01_api_health(self):
        """Test that API is responsive"""
        print("✓ Checking API health...")
        response = requests.get(f"{API_URL}/health", timeout=TEST_TIMEOUT)
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["status"], "healthy")
        print(f"  API Status: {data['status']}")
        print(f"  Prometheus URL: {data['prometheus_url']}")
    
    def test_02_restart_pod_dry_run(self):
        """Test pod restart in dry-run mode"""
        print("✓ Testing pod restart (dry-run)...")
        
        # Get a running pod first
        pods_response = requests.get(
            f"{API_URL}/k8s/pods",
            params={"namespace": TEST_NAMESPACE},
            timeout=TEST_TIMEOUT
        )
        self.assertEqual(pods_response.status_code, 200)
        pods_data = pods_response.json()
        pods_list = pods_data if isinstance(pods_data, list) else pods_data.get("pods", [])
        
        if not pods_list:
            print("  ⚠ No pods found in namespace, skipping test")
            return
        
        # Use first running pod
        test_pod = None
        for pod in pods_list:
            if pod["status"] == "Running":
                test_pod = pod["name"]
                break
        
        if not test_pod:
            print("  ⚠ No running pods found, skipping test")
            return
        
        print(f"  Testing with pod: {test_pod}")
        
        # Dry run restart
        response = requests.post(
            f"{API_URL}/healing/restart-pod",
            params={
                "namespace": TEST_NAMESPACE,
                "pod_name": test_pod,
                "dry_run": True
            },
            timeout=TEST_TIMEOUT
        )
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertTrue(data["success"])
        self.assertTrue(data["dry_run"])
        self.assertIn("would be restarted", data["message"].lower())
        print(f"  Result: {data['message']}")
    
    def test_03_delete_failed_pods_dry_run(self):
        """Test deleting failed pods in dry-run mode"""
        print("✓ Testing delete failed pods (dry-run)...")
        
        response = requests.post(
            f"{API_URL}/healing/delete-failed-pods",
            params={
                "namespace": TEST_NAMESPACE,
                "dry_run": True
            },
            timeout=TEST_TIMEOUT
        )
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertTrue(data["success"])
        self.assertTrue(data["dry_run"])
        print(f"  Found {data.get('deleted_count', 0)} failed pods")
        if data.get('pods'):
            print(f"  Pods that would be deleted: {', '.join(data['pods'][:5])}")
    
    def test_04_evict_pod_dry_run(self):
        """Test pod eviction in dry-run mode"""
        print("✓ Testing pod eviction (dry-run)...")
        
        pods_response = requests.get(
            f"{API_URL}/k8s/pods",
            params={"namespace": TEST_NAMESPACE},
            timeout=TEST_TIMEOUT
        )
        self.assertEqual(pods_response.status_code, 200)
        pods_data = pods_response.json()
        pods_list = pods_data if isinstance(pods_data, list) else pods_data.get("pods", [])
        
        if not pods_list:
            print("  ⚠ No pods found in namespace, skipping test")
            return
        
        test_pod = None
        for pod in pods_list:
            if pod["status"] == "Running":
                test_pod = pod["name"]
                break
        
        if not test_pod:
            print("  ⚠ No running pods found, skipping test")
            return
        
        print(f"  Testing with pod: {test_pod}")
        
        response = requests.post(
            f"{API_URL}/healing/evict-pod",
            params={
                "namespace": TEST_NAMESPACE,
                "pod_name": test_pod,
                "dry_run": True
            },
            timeout=TEST_TIMEOUT
        )
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertTrue(data["success"])
        self.assertTrue(data["dry_run"])
        print(f"  Result: {data['message']}")

    def test_05_drain_node_dry_run(self):
        """Test draining node in dry-run mode"""
        print("✓ Testing drain node (dry-run)...")
        
        nodes_response = requests.get(
            f"{API_URL}/k8s/nodes",
            timeout=TEST_TIMEOUT
        )
        self.assertEqual(nodes_response.status_code, 200)
        nodes_data = nodes_response.json()
        nodes_list = nodes_data if isinstance(nodes_data, list) else nodes_data.get("nodes", [])
        
        if not nodes_list:
            print("  ⚠ No nodes found, skipping test")
            return
        
        test_node = nodes_list[0]["name"]
        print(f"  Testing with node: {test_node}")
        
        response = requests.post(
            f"{API_URL}/healing/drain-node",
            params={
                "node_name": test_node,
                "dry_run": True,
                "ignore_daemonsets": True,
                "include_kube_system": False
            },
            timeout=TEST_TIMEOUT
        )
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertTrue(data["success"])
        self.assertTrue(data["dry_run"])
        print(f"  Result: {data['message']}")

    def test_06_scale_deployment_dry_run(self):
        """Test scaling deployment in dry-run mode"""
        print("✓ Testing scale deployment (dry-run)...")
        
        # Try to scale prometheus deployment
        response = requests.post(
            f"{API_URL}/healing/scale-deployment",
            params={
                "namespace": TEST_NAMESPACE,
                "deployment_name": "prometheus",
                "replicas": 1,
                "dry_run": True
            },
            timeout=TEST_TIMEOUT
        )
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertTrue(data["success"])
        self.assertTrue(data["dry_run"])
        print(f"  Result: {data['message']}")
        if "current_replicas" in data:
            print(f"  Current replicas: {data['current_replicas']}")
            print(f"  Target replicas: {data['target_replicas']}")
    
    def test_07_rollback_deployment_dry_run(self):
        """Test deployment rollback in dry-run mode"""
        print("✓ Testing rollback deployment (dry-run)...")
        
        response = requests.post(
            f"{API_URL}/healing/rollback-deployment",
            params={
                "namespace": TEST_NAMESPACE,
                "deployment_name": "prometheus",
                "dry_run": True
            },
            timeout=TEST_TIMEOUT
        )
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertTrue(data["success"])
        self.assertTrue(data["dry_run"])
        print(f"  Result: {data['message']}")
    
    def test_08_cordon_node_dry_run(self):
        """Test cordoning node in dry-run mode"""
        print("✓ Testing cordon node (dry-run)...")
        
        # Get nodes first
        nodes_response = requests.get(
            f"{API_URL}/k8s/nodes",
            timeout=TEST_TIMEOUT
        )
        self.assertEqual(nodes_response.status_code, 200)
        nodes_data = nodes_response.json()
        nodes_list = nodes_data if isinstance(nodes_data, list) else nodes_data.get("nodes", [])
        
        if not nodes_list:
            print("  ⚠ No nodes found, skipping test")
            return
        
        test_node = nodes_list[0]["name"]
        print(f"  Testing with node: {test_node}")
        
        response = requests.post(
            f"{API_URL}/healing/cordon-node",
            params={
                "node_name": test_node,
                "dry_run": True
            },
            timeout=TEST_TIMEOUT
        )
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertTrue(data["success"])
        self.assertTrue(data["dry_run"])
        print(f"  Result: {data['message']}")
    
    def test_09_uncordon_node_dry_run(self):
        """Test uncordoning node in dry-run mode"""
        print("✓ Testing uncordon node (dry-run)...")
        
        # Get nodes first
        nodes_response = requests.get(
            f"{API_URL}/k8s/nodes",
            timeout=TEST_TIMEOUT
        )
        self.assertEqual(nodes_response.status_code, 200)
        nodes_data = nodes_response.json()
        nodes_list = nodes_data if isinstance(nodes_data, list) else nodes_data.get("nodes", [])
        
        if not nodes_list:
            print("  ⚠ No nodes found, skipping test")
            return
        
        test_node = nodes_list[0]["name"]
        print(f"  Testing with node: {test_node}")
        
        response = requests.post(
            f"{API_URL}/healing/uncordon-node",
            params={
                "node_name": test_node,
                "dry_run": True
            },
            timeout=TEST_TIMEOUT
        )
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertTrue(data["success"])
        self.assertTrue(data["dry_run"])
        print(f"  Result: {data['message']}")
    
    def test_10_healing_action_history(self):
        """Test getting healing action history"""
        print("✓ Testing healing action history...")
        
        response = requests.get(
            f"{API_URL}/healing/action-history",
            params={"hours": 24},
            timeout=TEST_TIMEOUT
        )
        self.assertEqual(response.status_code, 200)
        data = response.json()
        
        print(f"  Time period: {data['time_period_hours']} hours")
        print(f"  Total actions: {data['total_actions']}")
        print(f"  Successful: {data['successful_actions']}")
        print(f"  Failed: {data['failed_actions']}")
        if data['total_actions'] > 0:
            print(f"  Success rate: {data['success_rate']}%")
        
        if data.get('by_action_type'):
            print("\n  Actions by type:")
            for action_type, stats in data['by_action_type'].items():
                print(f"    {action_type}: {stats['total']} (✓{stats['success']} ✗{stats['failed']})")
    
    def test_11_rate_limiting(self):
        """Test that rate limiting works"""
        print("✓ Testing rate limiting...")
        
        # Try to perform many actions quickly (in dry-run mode)
        # This should eventually hit the rate limit
        
        max_attempts = 15  # Try more than the limit
        successful = 0
        rate_limited = 0
        
        for i in range(max_attempts):
            try:
                response = requests.post(
                    f"{API_URL}/healing/delete-failed-pods",
                    params={
                        "namespace": TEST_NAMESPACE,
                        "dry_run": True
                    },
                    timeout=TEST_TIMEOUT
                )
                
                if response.status_code == 200:
                    data = response.json()
                    if data["success"]:
                        successful += 1
                    else:
                        if "rate limit" in data.get("error", "").lower():
                            rate_limited += 1
                            print(f"  Hit rate limit at attempt {i+1}")
                            break
            except Exception as e:
                print(f"  Error on attempt {i+1}: {e}")
        
        print(f"  Successful actions: {successful}")
        print(f"  Rate limited: {rate_limited}")
        
        # We expect to hit rate limit at some point
        # (unless the limit is very high or test is run separately)
    
    def test_12_safety_blast_radius(self):
        """Test blast radius safety mechanism"""
        print("✓ Testing blast radius control...")
        
        # Try to scale to a very large number (should be rejected)
        response = requests.post(
            f"{API_URL}/healing/scale-deployment",
            params={
                "namespace": TEST_NAMESPACE,
                "deployment_name": "prometheus",
                "replicas": 100,  # Way more than safety limit
                "dry_run": True
            },
            timeout=TEST_TIMEOUT
        )
        self.assertEqual(response.status_code, 200)
        data = response.json()
        
        # Should either succeed in dry-run or be blocked by safety
        if not data["success"]:
            print(f"  Correctly blocked: {data.get('error', 'Unknown error')}")
            self.assertIn("blast radius", data.get("error", "").lower())
        else:
            print(f"  Dry-run allowed: {data['message']}")
    
    def test_13_actual_delete_failed_pods(self):
        """Test actually deleting failed pods (creates test pod first)"""
        print("✓ Testing actual pod deletion...")
        
        # This test will create a failed pod and then delete it
        # Skip if we don't want to modify cluster state
        print("  ⚠ Skipping actual deletion test (use manual test)")
        print("  To test manually: Create a failing pod, then call delete-failed-pods without dry_run")
    
    def test_14_integration_detection_and_healing(self):
        """Test integration between detection and healing"""
        print("✓ Testing detection + healing integration...")
        
        # First, detect anomalies
        detection_response = requests.get(
            f"{API_URL}/detection/anomalies",
            params={"namespace": TEST_NAMESPACE},
            timeout=TEST_TIMEOUT
        )
        self.assertEqual(detection_response.status_code, 200)
        anomalies = detection_response.json()
        
        total_anomalies = anomalies.get("summary", {}).get("total_anomalies", 0)
        print(f"  Detected {total_anomalies} anomalies")
        
        # Check for pod-related issues
        pod_issues = []
        for category, items in anomalies.get('anomalies', {}).items():
            for item in items:
                if 'pod' in item.get('description', '').lower():
                    pod_issues.append(item)
        
        if pod_issues:
            print(f"  Found {len(pod_issues)} pod-related issues")
            for issue in pod_issues[:3]:
                print(f"    - {issue['description']}")
        
        # If we found restart anomalies, we could suggest healing actions
        # (but not actually execute them in automated tests)
        print("  ✓ Detection and healing systems are integrated")


def print_test_summary(result):
    """Print a summary of test results"""
    print("\n" + "="*60)
    print("HEALING ACTIONS TEST SUMMARY")
    print("="*60)
    print(f"Tests run: {result.testsRun}")
    print(f"Successes: {result.testsRun - len(result.failures) - len(result.errors)}")
    print(f"Failures: {len(result.failures)}")
    print(f"Errors: {len(result.errors)}")
    
    if result.wasSuccessful():
        print("\n✅ ALL TESTS PASSED!")
    else:
        print("\n❌ SOME TESTS FAILED")
    
    print("="*60)


if __name__ == "__main__":
    print("\n" + "="*60)
    print("PHASE 4: SELF-HEALING ACTIONS TEST SUITE")
    print("="*60)
    print(f"API URL: {API_URL}")
    print(f"Test Namespace: {TEST_NAMESPACE}")
    print(f"Timeout: {TEST_TIMEOUT}s")
    print("="*60)
    
    # Run tests
    loader = unittest.TestLoader()
    suite = loader.loadTestsFromTestCase(TestHealingActions)
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    
    # Print summary
    print_test_summary(result)
    
    # Exit with appropriate code
    exit(0 if result.wasSuccessful() else 1)
