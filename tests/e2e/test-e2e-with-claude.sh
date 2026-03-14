#!/bin/bash
# End-to-End Test with Claude Desktop Integration
# This script deploys test infrastructure, lets you verify with Claude, then cleans up

set -e

NAMESPACE="intelligent-sre"
API_URL="http://localhost:30080"

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
MAGENTA='\033[0;35m'
CYAN='\033[0;36m'
NC='\033[0m' # No Color
BOLD='\033[1m'

# Cleanup function
cleanup_test_pods() {
    echo ""
    echo -e "${YELLOW}Cleaning up test infrastructure...${NC}"
    
    # Delete all test pods
    kubectl delete pod cpu-stress-test -n $NAMESPACE --force --grace-period=0 2>/dev/null || true
    kubectl delete pod memory-stress-test -n $NAMESPACE --force --grace-period=0 2>/dev/null || true
    kubectl delete pod crash-loop-test -n $NAMESPACE --force --grace-period=0 2>/dev/null || true
    kubectl delete pod image-pull-test -n $NAMESPACE --force --grace-period=0 2>/dev/null || true
    kubectl delete pod cascade-test-1 -n $NAMESPACE --force --grace-period=0 2>/dev/null || true
    kubectl delete pod cascade-test-2 -n $NAMESPACE --force --grace-period=0 2>/dev/null || true
    kubectl delete pod cascade-test-3 -n $NAMESPACE --force --grace-period=0 2>/dev/null || true
    
    echo -e "${GREEN}✓ Cleanup complete${NC}"
}

# Trap to ensure cleanup on script exit
trap cleanup_test_pods EXIT

# Print header
print_header() {
    echo ""
    echo -e "${BLUE}${BOLD}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
    echo -e "${BLUE}${BOLD}$1${NC}"
    echo -e "${BLUE}${BOLD}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
    echo ""
}

# Print step
print_step() {
    echo ""
    echo -e "${CYAN}${BOLD}▶ $1${NC}"
}

# Wait for user
wait_for_user() {
    echo ""
    echo -e "${YELLOW}${BOLD}Press Enter to continue...${NC}"
    read
}

# Main script
print_header "End-to-End Test with Claude Desktop Integration"

echo -e "${BOLD}This test will:${NC}"
echo "  1. ✅ Verify baseline system health"
echo "  2. 🚀 Deploy test infrastructure (stress pods, failing pods)"
echo "  3. ⏱️  Wait for issues to develop"
echo "  4. 🤖 Give you time to test with Claude Desktop"
echo "  5. 🧹 Automatically clean up test infrastructure"
echo ""
echo -e "${YELLOW}Note: Cleanup happens automatically when script exits${NC}"
echo ""

wait_for_user

# ============================================
# STEP 1: Baseline Health Check
# ============================================
print_header "STEP 1: Baseline Health Check"

print_step "Checking API health..."
if curl -s "$API_URL/health" | grep -q "healthy"; then
    echo -e "${GREEN}✓ API is healthy${NC}"
else
    echo -e "${RED}✗ API is not responding${NC}"
    exit 1
fi

print_step "Getting baseline health score..."
curl -s "$API_URL/detection/health-score?namespace=$NAMESPACE" | python3 -m json.tool | head -15

print_step "Checking current anomalies..."
BASELINE_ANOMALIES=$(curl -s "$API_URL/detection/anomalies?namespace=$NAMESPACE" | python3 -c "import sys, json; data=json.load(sys.stdin); print(data.get('total_anomalies', data.get('anomaly_summary', {}).get('total_anomalies', 0)))" 2>/dev/null || echo "0")
echo -e "${BLUE}Current anomalies: $BASELINE_ANOMALIES${NC}"

wait_for_user

# ============================================
# STEP 2: Deploy Test Infrastructure
# ============================================
print_header "STEP 2: Deploying Test Infrastructure"

print_step "1/5 - Creating CPU stress test pod..."
cat <<EOF | kubectl apply -f -
apiVersion: v1
kind: Pod
metadata:
  name: cpu-stress-test
  namespace: $NAMESPACE
  labels:
    app: e2e-test
    test-type: cpu-stress
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
    - "600s"
EOF
echo -e "${GREEN}✓ CPU stress pod created${NC}"
sleep 2

print_step "2/5 - Creating memory stress test pod..."
cat <<EOF | kubectl apply -f -
apiVersion: v1
kind: Pod
metadata:
  name: memory-stress-test
  namespace: $NAMESPACE
  labels:
    app: e2e-test
    test-type: memory-stress
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
    - "600s"
EOF
echo -e "${GREEN}✓ Memory stress pod created${NC}"
sleep 2

print_step "3/5 - Creating crash loop test pod..."
cat <<EOF | kubectl apply -f -
apiVersion: v1
kind: Pod
metadata:
  name: crash-loop-test
  namespace: $NAMESPACE
  labels:
    app: e2e-test
    test-type: crash-loop
spec:
  restartPolicy: Always
  containers:
  - name: crash-container
    image: busybox
    command: ["/bin/sh"]
    args: ["-c", "echo 'Starting...'; sleep 10; echo 'Crashing!'; exit 1"]
EOF
echo -e "${GREEN}✓ Crash loop pod created${NC}"
sleep 2

print_step "4/5 - Creating image pull error test pod..."
cat <<EOF | kubectl apply -f -
apiVersion: v1
kind: Pod
metadata:
  name: image-pull-test
  namespace: $NAMESPACE
  labels:
    app: e2e-test
    test-type: image-pull-error
spec:
  containers:
  - name: bad-image
    image: nonexistent/invalid-image:bad-tag-12345
EOF
echo -e "${GREEN}✓ Image pull error pod created${NC}"
sleep 2

print_step "5/5 - Creating cascading failure test pods..."
for i in 1 2 3; do
cat <<EOF | kubectl apply -f -
apiVersion: v1
kind: Pod
metadata:
  name: cascade-test-$i
  namespace: $NAMESPACE
  labels:
    app: e2e-test
    test-type: cascading-failure
spec:
  restartPolicy: Always
  containers:
  - name: failing-container
    image: busybox
    command: ["/bin/sh"]
    args: ["-c", "sleep $((i * 5)); exit 1"]
EOF
done
echo -e "${GREEN}✓ Cascading failure pods created (3 pods)${NC}"

print_step "Waiting for pods to initialize..."
sleep 10

echo ""
echo -e "${MAGENTA}${BOLD}Test Infrastructure Deployed:${NC}"
kubectl get pods -n $NAMESPACE -l app=e2e-test --no-headers | awk '{printf "  • %-25s %s\n", $1, $3}'

wait_for_user

# ============================================
# STEP 3: Wait for Issues to Develop
# ============================================
print_header "STEP 3: Waiting for Issues to Develop"

echo -e "${YELLOW}This will take about 2 minutes to allow:${NC}"
echo "  • CPU/Memory stress to register in metrics"
echo "  • Crash loop pod to restart multiple times"
echo "  • Image pull errors to be recorded"
echo "  • Cascading failures to propagate"
echo ""

for i in {120..1}; do
    printf "\r${YELLOW}⏱️  Time remaining: %02d:%02d ${NC}" $((i/60)) $((i%60))
    sleep 1
done
echo ""
echo -e "${GREEN}✓ Issues should now be detectable${NC}"

wait_for_user

# ============================================
# STEP 4: Show Current State & Detection Results
# ============================================
print_header "STEP 4: Detection Results"

print_step "Current pod status..."
kubectl get pods -n $NAMESPACE -l app=e2e-test

echo ""
print_step "Detecting anomalies..."
curl -s "$API_URL/detection/anomalies?namespace=$NAMESPACE" | python3 -m json.tool | head -40

echo ""
print_step "Calculating health score..."
curl -s "$API_URL/detection/health-score?namespace=$NAMESPACE" | python3 -m json.tool | head -20

echo ""
print_step "Detecting patterns..."
curl -s "$API_URL/detection/patterns?namespace=$NAMESPACE" | python3 -m json.tool | head -40

echo ""
print_step "Detecting correlations..."
curl -s "$API_URL/detection/correlations?namespace=$NAMESPACE" | python3 -m json.tool | head -40

wait_for_user

# ============================================
# STEP 5: Claude Desktop Testing Time
# ============================================
print_header "STEP 5: Test with Claude Desktop"

echo -e "${BOLD}${MAGENTA}🤖 Now it's time to test with Claude Desktop!${NC}"
echo ""
echo -e "${BOLD}Open Claude Desktop and try these prompts:${NC}"
echo ""
echo -e "${CYAN}Basic Health Checks:${NC}"
echo '  • "What is the health score of my intelligent-sre namespace?"'
echo '  • "Is my system healthy?"'
echo '  • "Show me all pods in intelligent-sre namespace"'
echo ""
echo -e "${CYAN}Anomaly Detection:${NC}"
echo '  • "Detect all anomalies in intelligent-sre namespace"'
echo '  • "Are there any CPU or memory anomalies?"'
echo '  • "Show me pods with high restart counts"'
echo '  • "Which pods are pending and why?"'
echo ""
echo -e "${CYAN}Pattern Recognition:${NC}"
echo '  • "Show me patterns in pod failures"'
echo '  • "Are there any recurring issues?"'
echo '  • "Detect cyclic problems in my cluster"'
echo ""
echo -e "${CYAN}Correlation Analysis:${NC}"
echo '  • "Show correlations between restarts and events"'
echo '  • "Are there any cascading failures?"'
echo '  • "What is causing the pod failures?"'
echo ""
echo -e "${CYAN}Comprehensive Analysis:${NC}"
echo '  • "Run comprehensive analysis on intelligent-sre namespace"'
echo '  • "Give me a full system report"'
echo '  • "What issues should I be concerned about?"'
echo ""
echo -e "${CYAN}Troubleshooting:${NC}"
echo '  • "Which pods are failing and why?"'
echo '  • "Show me logs from crash-loop-test pod"'
echo '  • "Describe the cpu-stress-test pod"'
echo ""
echo -e "${YELLOW}${BOLD}Expected Claude Behavior:${NC}"
echo "  ✓ Claude should invoke MCP tools (detect_anomalies, get_health_score, etc.)"
echo "  ✓ Should detect 5-7 anomalies (CPU, memory, restarts, pending pods)"
echo "  ✓ Should show health score: 0-50 (critical) 🔥"
echo "  ✓ Should identify recurring failures pattern"
echo "  ✓ Should detect cascading failures correlation"
echo "  ✓ Should provide actionable recommendations"
echo ""
echo -e "${YELLOW}${BOLD}Take your time to test all prompts!${NC}"
echo ""
echo -e "${RED}${BOLD}⚠️  When you're done testing with Claude, press Enter to clean up test pods.${NC}"

wait_for_user

# ============================================
# STEP 6: Final State Check
# ============================================
print_header "STEP 6: Final State Check"

print_step "Final health score..."
curl -s "$API_URL/detection/health-score?namespace=$NAMESPACE" | python3 -m json.tool | head -15

print_step "Total anomalies detected..."
FINAL_ANOMALIES=$(curl -s "$API_URL/detection/anomalies?namespace=$NAMESPACE" | python3 -c "import sys, json; data=json.load(sys.stdin); print(data.get('total_anomalies', data.get('anomaly_summary', {}).get('total_anomalies', 0)))" 2>/dev/null || echo "0")
echo -e "${BLUE}Final anomalies: $FINAL_ANOMALIES${NC}"
echo -e "${BLUE}Baseline was: $BASELINE_ANOMALIES${NC}"
echo -e "${MAGENTA}Detected: $((FINAL_ANOMALIES - BASELINE_ANOMALIES)) new anomalies${NC}"

print_step "Test pods status..."
kubectl get pods -n $NAMESPACE -l app=e2e-test

# ============================================
# Cleanup (automatic via trap)
# ============================================
print_header "STEP 7: Cleanup"

echo -e "${YELLOW}Test infrastructure will be cleaned up automatically...${NC}"
echo ""

# Cleanup happens via EXIT trap

print_header "✅ End-to-End Test Complete!"

echo -e "${GREEN}${BOLD}Summary:${NC}"
echo "  • Deployed 7 test pods with various failure modes"
echo "  • Waited for issues to develop in metrics"
echo "  • Detection engines identified anomalies"
echo "  • You tested with Claude Desktop"
echo "  • Test infrastructure cleaned up"
echo ""
echo -e "${CYAN}To verify cleanup:${NC}"
echo "  kubectl get pods -n $NAMESPACE -l app=e2e-test"
echo ""
echo -e "${CYAN}To verify system is back to baseline:${NC}"
echo "  curl http://localhost:30080/detection/health-score?namespace=intelligent-sre | python3 -m json.tool"
echo ""
echo -e "${GREEN}${BOLD}Test completed successfully! 🎉${NC}"
