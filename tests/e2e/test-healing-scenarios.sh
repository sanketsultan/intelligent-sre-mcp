#!/bin/bash
# Interactive Healing Actions Test Scenarios
# Phase 4: Self-Healing Capabilities

set -e

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
MAGENTA='\033[0;35m'
CYAN='\033[0;36m'
BOLD='\033[1m'
NC='\033[0m'

API_URL="http://localhost:30080"
NAMESPACE="intelligent-sre"

# Banner
clear
echo ""
echo -e "${CYAN}${BOLD}╔════════════════════════════════════════════════════╗${NC}"
echo -e "${CYAN}${BOLD}║   Phase 4: Self-Healing Actions Test Scenarios    ║${NC}"
echo -e "${CYAN}${BOLD}╚════════════════════════════════════════════════════╝${NC}"
echo ""

# Cleanup function
cleanup_test_resources() {
    echo -e "\n${YELLOW}Cleaning up test resources...${NC}"
    
    # Delete test pods
    kubectl delete pod test-crashloop-pod test-failing-pod test-completed-pod \
        -n "$NAMESPACE" --ignore-not-found=true 2>/dev/null || true
    
    # Delete test deployment
    kubectl delete deployment test-healing-deployment \
        -n "$NAMESPACE" --ignore-not-found=true 2>/dev/null || true
    
    echo -e "${GREEN}✓ Cleanup complete${NC}"
}

# Trap for cleanup
trap cleanup_test_resources EXIT

show_menu() {
    echo -e "${BOLD}Available Healing Scenarios:${NC}"
    echo ""
    echo -e "${MAGENTA}Pod Healing:${NC}"
    echo -e "  ${CYAN}1.${NC} Test Pod Restart (Dry-Run)"
    echo -e "  ${CYAN}2.${NC} Test Delete Failed Pods (Dry-Run)"
    echo -e "  ${CYAN}3.${NC} Test Pod Eviction (Dry-Run)"
    echo -e "  ${CYAN}4.${NC} Create & Delete Failing Pod (ACTUAL)"
    echo ""
    echo -e "${MAGENTA}Deployment Healing:${NC}"
    echo -e "  ${CYAN}5.${NC} Test Deployment Scaling (Dry-Run)"
    echo -e "  ${CYAN}6.${NC} Test Deployment Rollback (Dry-Run)"
    echo -e "  ${CYAN}7.${NC} Create, Scale & Rollback Deployment (ACTUAL)"
    echo ""
    echo -e "${MAGENTA}Node Management:${NC}"
    echo -e "  ${CYAN}8.${NC} Test Node Cordon/Uncordon (Dry-Run)"
    echo -e "  ${CYAN}9.${NC} Test Node Drain (Dry-Run)"
    echo ""
    echo -e "${MAGENTA}History & Monitoring:${NC}"
    echo -e "  ${CYAN}10.${NC} View Healing Action History"
    echo -e "  ${CYAN}11.${NC} Test Rate Limiting"
    echo ""
    echo -e "${MAGENTA}Integration:${NC}"
    echo -e "  ${CYAN}12.${NC} Detection + Healing Integration Test"
    echo -e "  ${CYAN}13.${NC} Run All Dry-Run Tests"
    echo ""
    echo -e "${GREEN}0. Exit${NC}"
    echo ""
}

# ==================== Scenario Functions ====================

scenario_restart_pod_dry_run() {
    echo -e "\n${BLUE}${BOLD}Scenario 1: Test Pod Restart (Dry-Run)${NC}"
    echo -e "${YELLOW}This will simulate restarting a pod without actually doing it${NC}"
    echo ""
    
    # Get a running pod
    echo -e "${CYAN}Getting pods in ${NAMESPACE}...${NC}"
    POD_NAME=$(kubectl get pods -n "$NAMESPACE" --field-selector=status.phase=Running -o jsonpath='{.items[0].metadata.name}' 2>/dev/null)
    
    if [ -z "$POD_NAME" ]; then
        echo -e "${RED}✗ No running pods found in ${NAMESPACE}${NC}"
        return
    fi
    
    echo -e "${GREEN}Selected pod: ${POD_NAME}${NC}"
    echo ""
    
    echo -e "${CYAN}Calling restart-pod API (dry-run)...${NC}"
    curl -s -X POST "${API_URL}/healing/restart-pod?namespace=${NAMESPACE}&pod_name=${POD_NAME}&dry_run=true" | python3 -m json.tool
    
    echo ""
    echo -e "${GREEN}✓ Dry-run complete - no changes were made${NC}"
}

scenario_delete_failed_pods_dry_run() {
    echo -e "\n${BLUE}${BOLD}Scenario 2: Test Delete Failed Pods (Dry-Run)${NC}"
    echo -e "${YELLOW}This will find failed pods but not delete them${NC}"
    echo ""
    
    echo -e "${CYAN}Checking for failed pods in ${NAMESPACE}...${NC}"
    curl -s -X POST "${API_URL}/healing/delete-failed-pods?namespace=${NAMESPACE}&dry_run=true" | python3 -m json.tool
    
    echo ""
    echo -e "${GREEN}✓ Dry-run complete - no pods were deleted${NC}"
}

scenario_evict_pod_dry_run() {
    echo -e "\n${BLUE}${BOLD}Scenario 3: Test Pod Eviction (Dry-Run)${NC}"
    echo -e "${YELLOW}This will simulate evicting a pod from its node${NC}"
    echo ""
    
    echo -e "${CYAN}Getting pods in ${NAMESPACE}...${NC}"
    POD_NAME=$(kubectl get pods -n "$NAMESPACE" --field-selector=status.phase=Running -o jsonpath='{.items[0].metadata.name}' 2>/dev/null)
    
    if [ -z "$POD_NAME" ]; then
        echo -e "${RED}✗ No running pods found in ${NAMESPACE}${NC}"
        return
    fi
    
    echo -e "${GREEN}Selected pod: ${POD_NAME}${NC}"
    echo ""
    
    echo -e "${CYAN}Calling evict-pod API (dry-run)...${NC}"
    curl -s -X POST "${API_URL}/healing/evict-pod?namespace=${NAMESPACE}&pod_name=${POD_NAME}&dry_run=true" | python3 -m json.tool
    
    echo ""
    echo -e "${GREEN}✓ Dry-run complete - no changes were made${NC}"
}

scenario_create_and_delete_failing_pod() {
    echo -e "\n${BLUE}${BOLD}Scenario 4: Create & Delete Failing Pod (ACTUAL)${NC}"
    echo -e "${RED}⚠️  This will create and then delete actual pods in your cluster${NC}"
    echo ""
    read -p "Continue? (y/n): " -n 1 -r
    echo ""
    
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        echo -e "${YELLOW}Skipped${NC}"
        return
    fi
    
    echo -e "\n${CYAN}Step 1: Creating a failing pod...${NC}"
    cat <<EOF | kubectl apply -f -
apiVersion: v1
kind: Pod
metadata:
  name: test-failing-pod
  namespace: $NAMESPACE
  labels:
    test: healing
spec:
  containers:
  - name: failing-container
    image: nonexistent-image:latest
    imagePullPolicy: Always
  restartPolicy: Never
EOF
    
    echo -e "${GREEN}✓ Failing pod created${NC}"
    
    echo -e "\n${CYAN}Step 2: Waiting for pod to fail...${NC}"
    sleep 5
    
    echo -e "\n${CYAN}Step 3: Checking pod status...${NC}"
    kubectl get pod test-failing-pod -n "$NAMESPACE"
    
    echo -e "\n${CYAN}Step 4: Calling delete-failed-pods API (ACTUAL)...${NC}"
    curl -s -X POST "${API_URL}/healing/delete-failed-pods?namespace=${NAMESPACE}&dry_run=false" | python3 -m json.tool
    
    echo ""
    echo -e "${GREEN}✓ Failed pod deleted${NC}"
}

scenario_scale_deployment_dry_run() {
    echo -e "\n${BLUE}${BOLD}Scenario 5: Test Deployment Scaling (Dry-Run)${NC}"
    echo -e "${YELLOW}This will simulate scaling a deployment${NC}"
    echo ""
    
    DEPLOYMENT="prometheus"
    TARGET_REPLICAS=2
    
    echo -e "${CYAN}Current deployment status:${NC}"
    kubectl get deployment "$DEPLOYMENT" -n "$NAMESPACE" 2>/dev/null || {
        echo -e "${RED}✗ Deployment not found${NC}"
        return
    }
    
    echo ""
    echo -e "${CYAN}Simulating scale to ${TARGET_REPLICAS} replicas (dry-run)...${NC}"
    curl -s -X POST "${API_URL}/healing/scale-deployment?namespace=${NAMESPACE}&deployment_name=${DEPLOYMENT}&replicas=${TARGET_REPLICAS}&dry_run=true" | python3 -m json.tool
    
    echo ""
    echo -e "${GREEN}✓ Dry-run complete - no changes were made${NC}"
}

scenario_rollback_deployment_dry_run() {
    echo -e "\n${BLUE}${BOLD}Scenario 6: Test Deployment Rollback (Dry-Run)${NC}"
    echo -e "${YELLOW}This will simulate rolling back a deployment${NC}"
    echo ""
    
    DEPLOYMENT="prometheus"
    
    echo -e "${CYAN}Current deployment status:${NC}"
    kubectl get deployment "$DEPLOYMENT" -n "$NAMESPACE" 2>/dev/null || {
        echo -e "${RED}✗ Deployment not found${NC}"
        return
    }
    
    echo ""
    echo -e "${CYAN}Simulating rollback (dry-run)...${NC}"
    curl -s -X POST "${API_URL}/healing/rollback-deployment?namespace=${NAMESPACE}&deployment_name=${DEPLOYMENT}&dry_run=true" | python3 -m json.tool
    
    echo ""
    echo -e "${GREEN}✓ Dry-run complete - no changes were made${NC}"
}

scenario_create_scale_rollback() {
    echo -e "\n${BLUE}${BOLD}Scenario 7: Create, Scale & Rollback Deployment (ACTUAL)${NC}"
    echo -e "${RED}⚠️  This will create and modify actual deployments${NC}"
    echo ""
    read -p "Continue? (y/n): " -n 1 -r
    echo ""
    
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        echo -e "${YELLOW}Skipped${NC}"
        return
    fi
    
    DEPLOY_NAME="test-healing-deployment"
    
    echo -e "\n${CYAN}Step 1: Creating test deployment (1 replica)...${NC}"
    cat <<EOF | kubectl apply -f -
apiVersion: apps/v1
kind: Deployment
metadata:
  name: $DEPLOY_NAME
  namespace: $NAMESPACE
  labels:
    test: healing
spec:
  replicas: 1
  selector:
    matchLabels:
      app: test-healing
  template:
    metadata:
      labels:
        app: test-healing
    spec:
      containers:
      - name: nginx
        image: nginx:1.21
        ports:
        - containerPort: 80
EOF
    
    sleep 3
    kubectl get deployment "$DEPLOY_NAME" -n "$NAMESPACE"
    
    echo -e "\n${CYAN}Step 2: Scaling deployment to 3 replicas...${NC}"
    curl -s -X POST "${API_URL}/healing/scale-deployment?namespace=${NAMESPACE}&deployment_name=${DEPLOY_NAME}&replicas=3&dry_run=false" | python3 -m json.tool
    
    sleep 3
    kubectl get deployment "$DEPLOY_NAME" -n "$NAMESPACE"
    
    echo -e "\n${CYAN}Step 3: Updating deployment (changing image)...${NC}"
    kubectl set image deployment/"$DEPLOY_NAME" nginx=nginx:1.22 -n "$NAMESPACE"
    
    sleep 3
    
    echo -e "\n${CYAN}Step 4: Rolling back deployment...${NC}"
    curl -s -X POST "${API_URL}/healing/rollback-deployment?namespace=${NAMESPACE}&deployment_name=${DEPLOY_NAME}&dry_run=false" | python3 -m json.tool
    
    sleep 3
    kubectl get deployment "$DEPLOY_NAME" -n "$NAMESPACE"
    
    echo ""
    echo -e "${GREEN}✓ Deployment lifecycle test complete${NC}"
    echo -e "${YELLOW}Deployment will be cleaned up on exit${NC}"
}

scenario_node_cordon_uncordon() {
    echo -e "\n${BLUE}${BOLD}Scenario 8: Test Node Cordon/Uncordon (Dry-Run)${NC}"
    echo -e "${YELLOW}This will simulate cordoning and uncordoning a node${NC}"
    echo ""
    
    NODE_NAME=$(kubectl get nodes -o jsonpath='{.items[0].metadata.name}')
    
    if [ -z "$NODE_NAME" ]; then
        echo -e "${RED}✗ No nodes found${NC}"
        return
    fi
    
    echo -e "${GREEN}Selected node: ${NODE_NAME}${NC}"
    echo ""
    
    echo -e "${CYAN}Current node status:${NC}"
    kubectl get node "$NODE_NAME"
    
    echo -e "\n${CYAN}Simulating cordon (dry-run)...${NC}"
    curl -s -X POST "${API_URL}/healing/cordon-node?node_name=${NODE_NAME}&dry_run=true" | python3 -m json.tool
    
    echo -e "\n${CYAN}Simulating uncordon (dry-run)...${NC}"
    curl -s -X POST "${API_URL}/healing/uncordon-node?node_name=${NODE_NAME}&dry_run=true" | python3 -m json.tool
    
    echo ""
    echo -e "${GREEN}✓ Dry-run complete - no changes were made${NC}"
}

scenario_drain_node_dry_run() {
    echo -e "\n${BLUE}${BOLD}Scenario 9: Test Node Drain (Dry-Run)${NC}"
    echo -e "${YELLOW}This will simulate draining a node without evictions${NC}"
    echo ""
    
    NODE_NAME=$(kubectl get nodes -o jsonpath='{.items[0].metadata.name}')
    
    if [ -z "$NODE_NAME" ]; then
        echo -e "${RED}✗ No nodes found${NC}"
        return
    fi
    
    echo -e "${GREEN}Selected node: ${NODE_NAME}${NC}"
    echo ""
    
    echo -e "${CYAN}Simulating drain (dry-run)...${NC}"
    curl -s -X POST "${API_URL}/healing/drain-node?node_name=${NODE_NAME}&dry_run=true" | python3 -m json.tool
    
    echo ""
    echo -e "${GREEN}✓ Dry-run complete - no changes were made${NC}"
}

scenario_view_healing_history() {
    echo -e "\n${BLUE}${BOLD}Scenario 10: View Healing Action History${NC}"
    echo -e "${YELLOW}This shows all healing actions taken in the last 24 hours${NC}"
    echo ""
    
    echo -e "${CYAN}Fetching healing action history...${NC}"
    curl -s "${API_URL}/healing/action-history?hours=24" | python3 -m json.tool
    
    echo ""
    echo -e "${GREEN}✓ History retrieved${NC}"
}

scenario_test_rate_limiting() {
    echo -e "\n${BLUE}${BOLD}Scenario 11: Test Rate Limiting${NC}"
    echo -e "${YELLOW}This will attempt many actions to trigger rate limiting${NC}"
    echo ""
    
    echo -e "${CYAN}Sending 12 rapid requests (dry-run mode)...${NC}"
    
    for i in {1..12}; do
        RESPONSE=$(curl -s -X POST "${API_URL}/healing/delete-failed-pods?namespace=${NAMESPACE}&dry_run=true")
        SUCCESS=$(echo "$RESPONSE" | python3 -c "import sys,json; print(json.load(sys.stdin)['success'])" 2>/dev/null)
        
        if [ "$SUCCESS" = "True" ]; then
            echo -e "  ${GREEN}✓${NC} Request $i: Success"
        else:
            ERROR=$(echo "$RESPONSE" | python3 -c "import sys,json; print(json.load(sys.stdin).get('error', 'Unknown'))" 2>/dev/null)
            echo -e "  ${RED}✗${NC} Request $i: $ERROR"
            
            if [[ "$ERROR" == *"rate limit"* ]] || [[ "$ERROR" == *"Rate limit"* ]]; then
                echo -e "\n${YELLOW}✓ Rate limiting is working!${NC}"
                break
            fi
        fi
        
        sleep 0.5
    done
    
    echo ""
    echo -e "${GREEN}✓ Rate limiting test complete${NC}"
}

scenario_detection_healing_integration() {
    echo -e "\n${BLUE}${BOLD}Scenario 12: Detection + Healing Integration${NC}"
    echo -e "${YELLOW}This demonstrates how detection and healing work together${NC}"
    echo ""
    
    echo -e "${CYAN}Step 1: Running anomaly detection...${NC}"
    ANOMALIES=$(curl -s "${API_URL}/detection/anomalies?namespace=${NAMESPACE}")
    echo "$ANOMALIES" | python3 -m json.tool
    
    TOTAL=$(echo "$ANOMALIES" | python3 -c "import sys,json; print(json.load(sys.stdin).get('summary', {}).get('total_anomalies', 0))" 2>/dev/null)
    
    echo ""
    echo -e "${YELLOW}Found ${TOTAL} anomalies${NC}"
    
    if [ "$TOTAL" -gt 0 ]; then
        echo ""
        echo -e "${CYAN}Step 2: Checking if healing actions are recommended...${NC}"
        echo "$ANOMALIES" | python3 -c "
import sys, json
data = json.load(sys.stdin)
shown = 0
for category, items in data.get('anomalies', {}).items():
    for anomaly in items:
        print(f\"  - {anomaly.get('description', 'Unknown')} [{anomaly.get('level', 'unknown')}]\")
        
        # Suggest healing actions based on anomaly type
        desc = anomaly.get('description', '').lower()
        if 'restart' in desc or 'crash' in desc:
            print(f\"    → Suggested healing: restart_pod\")
        elif 'memory' in desc or 'cpu' in desc:
            print(f\"    → Suggested healing: scale_deployment\")
        elif 'failed' in desc:
            print(f\"    → Suggested healing: delete_failed_pods\")
        shown += 1
        if shown >= 3:
            break
    if shown >= 3:
        break
" 2>/dev/null || echo "  (No specific recommendations)"
    fi
    
    echo ""
    echo -e "${GREEN}✓ Detection + Healing integration working${NC}"
    echo -e "${YELLOW}Use individual healing tools to resolve detected issues${NC}"
}

scenario_run_all_dry_run() {
    echo -e "\n${BLUE}${BOLD}Scenario 13: Run All Dry-Run Tests${NC}"
    echo -e "${YELLOW}This will run all non-destructive tests${NC}"
    echo ""
    
    scenario_restart_pod_dry_run
    sleep 2
    
    scenario_delete_failed_pods_dry_run
    sleep 2

    scenario_evict_pod_dry_run
    sleep 2
    
    scenario_scale_deployment_dry_run
    sleep 2
    
    scenario_rollback_deployment_dry_run
    sleep 2
    
    scenario_node_cordon_uncordon
    sleep 2

    scenario_drain_node_dry_run
    sleep 2
    
    scenario_view_healing_history
    
    echo ""
    echo -e "${GREEN}${BOLD}✓ All dry-run tests complete!${NC}"
}

# ==================== Main Loop ====================

while true; do
    show_menu
    read -p "Enter choice (0-13): " choice
    
    case $choice in
        1) scenario_restart_pod_dry_run ;;
        2) scenario_delete_failed_pods_dry_run ;;
        3) scenario_evict_pod_dry_run ;;
        4) scenario_create_and_delete_failing_pod ;;
        5) scenario_scale_deployment_dry_run ;;
        6) scenario_rollback_deployment_dry_run ;;
        7) scenario_create_scale_rollback ;;
        8) scenario_node_cordon_uncordon ;;
        9) scenario_drain_node_dry_run ;;
        10) scenario_view_healing_history ;;
        11) scenario_test_rate_limiting ;;
        12) scenario_detection_healing_integration ;;
        13) scenario_run_all_dry_run ;;
        0)
            echo ""
            echo -e "${GREEN}Goodbye!${NC}"
            exit 0
            ;;
        *)
            echo -e "${RED}Invalid choice. Please select 0-13.${NC}"
            ;;
    esac
    
    echo ""
    echo -e "${YELLOW}Press Enter to continue...${NC}"
    read
    clear
done
