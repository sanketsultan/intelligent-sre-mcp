#!/bin/bash
# Test Scenarios for Intelligent SRE MCP
# This script creates various scenarios to test anomaly detection, pattern recognition, and correlation

set -e

NAMESPACE="intelligent-sre"
API_URL="http://localhost:30080"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

echo -e "${BLUE}========================================${NC}"
echo -e "${BLUE}Intelligent SRE MCP - Test Scenarios${NC}"
echo -e "${BLUE}Phase 2: Detection | Phase 3: Healing${NC}"
echo -e "${BLUE}========================================${NC}"
echo ""

# Function to print section headers
print_header() {
    echo ""
    echo -e "${GREEN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
    echo -e "${GREEN}$1${NC}"
    echo -e "${GREEN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
    echo ""
}

# Function to wait for user
wait_for_user() {
    echo ""
    echo -e "${YELLOW}Press Enter to continue...${NC}"
    read
}

# ============================================
# Scenario 1: Baseline Health Check
# ============================================
scenario_baseline() {
    print_header "Scenario 1: Baseline Health Check"
    echo "Testing current system health without any issues..."
    
    echo -e "${BLUE}1. Checking all pods:${NC}"
    curl -s "$API_URL/k8s/pods?namespace=$NAMESPACE" | python3 -m json.tool | head -20
    
    echo ""
    echo -e "${BLUE}2. Getting health score:${NC}"
    curl -s "$API_URL/detection/health-score?namespace=$NAMESPACE" | python3 -m json.tool | head -15
    
    echo ""
    echo -e "${BLUE}3. Detecting anomalies:${NC}"
    curl -s "$API_URL/detection/anomalies?namespace=$NAMESPACE" | python3 -m json.tool | head -20
    
    wait_for_user
}

# ============================================
# Scenario 2: High CPU Usage Simulation
# ============================================
scenario_high_cpu() {
    print_header "Scenario 2: High CPU Usage Simulation"
    echo "Creating a pod that consumes high CPU..."
    
    cat <<EOF | kubectl apply -f -
apiVersion: v1
kind: Pod
metadata:
  name: cpu-stress-test
  namespace: $NAMESPACE
  labels:
    app: stress-test
spec:
  containers:
  - name: cpu-stress
    image: progrium/stress
    resources:
      limits:
        cpu: "500m"
        memory: "128Mi"
      requests:
        cpu: "250m"
        memory: "64Mi"
    args:
    - --cpu
    - "2"
    - --timeout
    - "300s"
EOF

    echo ""
    echo "Waiting for pod to start..."
    sleep 10
    
    echo ""
    echo -e "${BLUE}Detecting CPU anomalies:${NC}"
    curl -s "$API_URL/detection/anomalies?namespace=$NAMESPACE" | python3 -m json.tool | grep -A 10 "cpu_anomalies"
    
    echo ""
    echo -e "${YELLOW}CPU stress test will run for 5 minutes. Check health score:${NC}"
    curl -s "$API_URL/detection/health-score?namespace=$NAMESPACE" | python3 -m json.tool | head -15
    
    wait_for_user
    
    echo "Cleaning up CPU stress test..."
    kubectl delete pod cpu-stress-test -n $NAMESPACE --force --grace-period=0
}

# ============================================
# Scenario 3: Memory Pressure Simulation
# ============================================
scenario_high_memory() {
    print_header "Scenario 3: High Memory Usage Simulation"
    echo "Creating a pod that consumes high memory..."
    
    cat <<EOF | kubectl apply -f -
apiVersion: v1
kind: Pod
metadata:
  name: memory-stress-test
  namespace: $NAMESPACE
  labels:
    app: stress-test
spec:
  containers:
  - name: memory-stress
    image: progrium/stress
    resources:
      limits:
        cpu: "100m"
        memory: "128Mi"
      requests:
        cpu: "50m"
        memory: "64Mi"
    args:
    - --vm
    - "1"
    - --vm-bytes
    - "100M"
    - --timeout
    - "300s"
EOF

    echo ""
    echo "Waiting for pod to start..."
    sleep 10
    
    echo ""
    echo -e "${BLUE}Detecting memory anomalies:${NC}"
    curl -s "$API_URL/detection/anomalies?namespace=$NAMESPACE" | python3 -m json.tool | grep -A 10 "memory_anomalies"
    
    echo ""
    echo -e "${BLUE}Comprehensive analysis:${NC}"
    curl -s "$API_URL/detection/comprehensive?namespace=$NAMESPACE" | python3 -m json.tool | head -40
    
    wait_for_user
    
    echo "Cleaning up memory stress test..."
    kubectl delete pod memory-stress-test -n $NAMESPACE --force --grace-period=0
}

# ============================================
# Scenario 4: Crash Loop Simulation
# ============================================
scenario_crash_loop() {
    print_header "Scenario 4: Crash Loop Simulation"
    echo "Creating a pod that crashes repeatedly..."
    
    cat <<EOF | kubectl apply -f -
apiVersion: v1
kind: Pod
metadata:
  name: crash-loop-test
  namespace: $NAMESPACE
  labels:
    app: crash-test
spec:
  restartPolicy: Always
  containers:
  - name: crash-container
    image: busybox
    command: ["/bin/sh"]
    args: ["-c", "echo 'Starting...'; sleep 5; echo 'Crashing!'; exit 1"]
EOF

    echo ""
    echo "Waiting for pod to crash a few times..."
    echo -e "${YELLOW}(This will take about 2-3 minutes)${NC}"
    sleep 120
    
    echo ""
    echo -e "${BLUE}Checking pod status:${NC}"
    kubectl get pod crash-loop-test -n $NAMESPACE
    
    echo ""
    echo -e "${BLUE}Detecting restart anomalies:${NC}"
    curl -s "$API_URL/detection/anomalies?namespace=$NAMESPACE" | python3 -m json.tool | grep -A 20 "restart_anomalies"
    
    echo ""
    echo -e "${BLUE}Detecting patterns (recurring failures):${NC}"
    curl -s "$API_URL/detection/patterns?namespace=$NAMESPACE" | python3 -m json.tool | grep -A 15 "recurring_failures"
    
    echo ""
    echo -e "${BLUE}Detecting correlations:${NC}"
    curl -s "$API_URL/detection/correlations?namespace=$NAMESPACE" | python3 -m json.tool | head -50
    
    wait_for_user
    
    echo "Cleaning up crash loop test..."
    kubectl delete pod crash-loop-test -n $NAMESPACE --force --grace-period=0
}

# ============================================
# Scenario 5: Image Pull Error
# ============================================
scenario_image_pull_error() {
    print_header "Scenario 5: Image Pull Error Simulation"
    echo "Creating a pod with non-existent image..."
    
    cat <<EOF | kubectl apply -f -
apiVersion: v1
kind: Pod
metadata:
  name: image-pull-test
  namespace: $NAMESPACE
  labels:
    app: image-pull-test
spec:
  containers:
  - name: bad-image
    image: nonexistent/image:invalid-tag-12345
EOF

    echo ""
    echo "Waiting for ImagePullBackOff..."
    sleep 30
    
    echo ""
    echo -e "${BLUE}Checking failing pods:${NC}"
    curl -s "$API_URL/k8s/pods/failing?namespace=$NAMESPACE" | python3 -m json.tool
    
    echo ""
    echo -e "${BLUE}Checking pod events:${NC}"
    kubectl describe pod image-pull-test -n $NAMESPACE | grep -A 10 "Events:"
    
    echo ""
    echo -e "${BLUE}Detecting anomalies:${NC}"
    curl -s "$API_URL/detection/anomalies?namespace=$NAMESPACE" | python3 -m json.tool | grep -A 10 "pending_pod_anomalies"
    
    wait_for_user
    
    echo "Cleaning up image pull test..."
    kubectl delete pod image-pull-test -n $NAMESPACE --force --grace-period=0
}

# ============================================
# Scenario 6: Multiple Pod Failures (Cascading)
# ============================================
scenario_cascading_failure() {
    print_header "Scenario 6: Cascading Failure Simulation"
    echo "Creating multiple failing pods to simulate cascading failure..."
    
    for i in 1 2 3; do
        cat <<EOF | kubectl apply -f -
apiVersion: v1
kind: Pod
metadata:
  name: cascade-test-$i
  namespace: $NAMESPACE
  labels:
    app: cascade-test
spec:
  restartPolicy: Always
  containers:
  - name: failing-container
    image: busybox
    command: ["/bin/sh"]
    args: ["-c", "sleep $((i * 5)); exit 1"]
EOF
    done
    
    echo ""
    echo "Waiting for multiple failures..."
    sleep 60
    
    echo ""
    echo -e "${BLUE}Checking all failing pods:${NC}"
    curl -s "$API_URL/k8s/pods/failing?namespace=$NAMESPACE" | python3 -m json.tool | head -30
    
    echo ""
    echo -e "${BLUE}Detecting cascading failures:${NC}"
    curl -s "$API_URL/detection/correlations?namespace=$NAMESPACE" | python3 -m json.tool | grep -A 20 "cascading"
    
    echo ""
    echo -e "${BLUE}Pattern analysis:${NC}"
    curl -s "$API_URL/detection/patterns?namespace=$NAMESPACE" | python3 -m json.tool | head -40
    
    wait_for_user
    
    echo "Cleaning up cascade tests..."
    kubectl delete pod cascade-test-1 cascade-test-2 cascade-test-3 -n $NAMESPACE --force --grace-period=0
}

# ============================================
# Scenario 7: Comprehensive Analysis
# ============================================
scenario_comprehensive() {
    print_header "Scenario 7: Comprehensive System Analysis"
    echo "Running full system analysis with all detection engines..."
    
    echo ""
    echo -e "${BLUE}Full comprehensive analysis:${NC}"
    curl -s "$API_URL/detection/comprehensive?namespace=$NAMESPACE" | python3 -m json.tool | head -100
    
    echo ""
    echo -e "${BLUE}Health score breakdown:${NC}"
    curl -s "$API_URL/detection/health-score" | python3 -m json.tool
    
    echo ""
    echo -e "${BLUE}Cluster-wide patterns:${NC}"
    curl -s "$API_URL/detection/patterns" | python3 -m json.tool | head -60
    
    wait_for_user
}

# ============================================
# Scenario 8: Custom Metric Spike Detection
# ============================================
scenario_metric_spike() {
    print_header "Scenario 8: Custom Metric Spike Detection"
    echo "Testing spike detection on various metrics..."
    
    echo ""
    echo -e "${BLUE}1. Detecting CPU spikes over last 1 hour:${NC}"
    curl -s "$API_URL/detection/spike?query=sum(rate(container_cpu_usage_seconds_total[5m]))%20by%20(pod)%20*%20100&duration=1h&spike_multiplier=2.0" | python3 -m json.tool | head -30
    
    echo ""
    echo -e "${BLUE}2. Detecting memory spikes:${NC}"
    curl -s "$API_URL/detection/spike?query=sum(container_memory_working_set_bytes)%20by%20(pod)&duration=1h&spike_multiplier=1.5" | python3 -m json.tool | head -30
    
    wait_for_user
}

# ============================================
# Scenario 9: Test with Claude Desktop
# ============================================
scenario_claude_test() {
    print_header "Scenario 9: Claude Desktop Integration Test"
    echo "Test prompts for Claude Desktop:"
    echo ""
    echo -e "${YELLOW}Copy and paste these prompts into Claude Desktop:${NC}"
    echo ""
    echo "1. \"What's the health score of my intelligent-sre namespace?\""
    echo "2. \"Detect all anomalies in my cluster\""
    echo "3. \"Show me any patterns in pod failures\""
    echo "4. \"Are there any correlations between restarts and events?\""
    echo "5. \"Run a comprehensive analysis on the intelligent-sre namespace\""
    echo "6. \"Which pods are failing and why?\""
    echo "7. \"Detect CPU spikes in the last hour\""
    echo "8. \"Is my system healthy?\""
    echo ""
    echo -e "${BLUE}Expected responses:${NC}"
    echo "- Claude should use the MCP tools (detect_anomalies, get_health_score, etc.)"
    echo "- Responses should include real data from your cluster"
    echo "- Health scores, anomaly counts, and recommendations should be displayed"
    echo ""
    wait_for_user
}

# ============================================
# Main Menu
# ============================================
show_menu() {
    echo ""
    echo -e "${BLUE}========================================${NC}"
    echo -e "${BLUE}Test Scenarios Menu${NC}"
    echo -e "${BLUE}========================================${NC}"
    echo ""
    echo -e "${GREEN}Detection Scenarios:${NC}"
    echo "1. Baseline Health Check (safe)"
    echo "2. High CPU Usage Simulation"
    echo "3. High Memory Usage Simulation"
    echo "4. Crash Loop Simulation"
    echo "5. Image Pull Error Simulation"
    echo "6. Cascading Failure Simulation"
    echo "7. Comprehensive Analysis"
    echo "8. Custom Metric Spike Detection"
    echo ""
    echo -e "${MAGENTA}Integration & Testing:${NC}"
    echo "9. Claude Desktop Integration Test"
    echo "10. Run All Detection Scenarios"
    echo "11. 🚀 End-to-End Test with Claude"
    echo "12. 🔧 Self-Healing Actions Test (Phase 3)"
    echo ""
    echo "0. Exit"
    echo ""
    echo -n "Select scenario: "
}

run_all_scenarios() {
    print_header "Running All Test Scenarios"
    echo "This will run all test scenarios sequentially..."
    echo -e "${YELLOW}Warning: This will create and delete test pods.${NC}"
    echo -e "${YELLOW}Estimated time: 15-20 minutes${NC}"
    echo ""
    read -p "Continue? (y/n) " -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        return
    fi
    
    scenario_baseline
    scenario_high_cpu
    scenario_high_memory
    scenario_crash_loop
    scenario_image_pull_error
    scenario_cascading_failure
    scenario_comprehensive
    scenario_metric_spike
    scenario_claude_test
    
    print_header "All Scenarios Complete!"
}

# Main loop
while true; do
    show_menu
    read choice
    
    case $choice in
        1) scenario_baseline ;;
        2) scenario_high_cpu ;;
        3) scenario_high_memory ;;
        4) scenario_crash_loop ;;
        5) scenario_image_pull_error ;;
        6) scenario_cascading_failure ;;
        7) scenario_comprehensive ;;
        8) scenario_metric_spike ;;
        9) scenario_claude_test ;;
        10) run_all_scenarios ;;
        11) 
            echo ""
            echo -e "${GREEN}Launching End-to-End Test with Claude Desktop...${NC}"
            echo ""
            # Get the directory where this script is located
            SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
            exec "$SCRIPT_DIR/test-e2e-with-claude.sh"
            ;;
        12)
            echo ""
            echo -e "${GREEN}Launching Self-Healing Actions Test...${NC}"
            echo ""
            SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
            exec "$SCRIPT_DIR/test-healing-scenarios.sh"
            ;;
        0) 
            echo ""
            echo -e "${GREEN}Goodbye!${NC}"
            exit 0
            ;;
        *)
            echo -e "${RED}Invalid option. Please try again.${NC}"
            ;;
    esac
done
