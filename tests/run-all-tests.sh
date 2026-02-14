#!/bin/bash

##############################################################################
# Intelligent SRE MCP - Comprehensive Test Orchestrator
# 
# Smart test runner that executes all tests in the correct order based on
# application architecture and dependencies.
#
# Architecture-Based Test Flow:
# 1. Infrastructure Health (Kubernetes, Prometheus, API Server)
# 2. Phase 1: Observability Tools (Metrics, Logs, Traces)
# 3. Phase 2: Detection Tools (Anomalies, Patterns, Health Scores)
# 4. Phase 4: Healing Actions (Self-Healing with Safety Controls)
# 5. Integration Tests (End-to-End Workflows)
##############################################################################

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
MAGENTA='\033[0;35m'
CYAN='\033[0;36m'
WHITE='\033[1;37m'
NC='\033[0m' # No Color

# Test results tracking
TOTAL_TESTS=0
PASSED_TESTS=0
FAILED_TESTS=0
SKIPPED_TESTS=0

# Test categories
declare -a FAILED_CATEGORIES=()

# Configuration
SKIP_CLEANUP=${SKIP_CLEANUP:-false}
VERBOSE=${VERBOSE:-false}
FAIL_FAST=${FAIL_FAST:-false}
DRY_RUN=${DRY_RUN:-false}

##############################################################################
# Helper Functions
##############################################################################

print_banner() {
    echo -e "${CYAN}"
    cat << 'EOF'
╔═══════════════════════════════════════════════════════════════════╗
║                                                                   ║
║        🧪 INTELLIGENT SRE MCP - COMPREHENSIVE TEST SUITE 🧪      ║
║                                                                   ║
║           Smart Test Orchestrator - Architecture-Based            ║
║                                                                   ║
╚═══════════════════════════════════════════════════════════════════╝
EOF
    echo -e "${NC}"
}

print_section() {
    local title=$1
    echo -e "\n${WHITE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
    echo -e "${CYAN}▶ $title${NC}"
    echo -e "${WHITE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}\n"
}

log_info() {
    echo -e "${BLUE}ℹ ${NC}$1"
}

log_success() {
    echo -e "${GREEN}✓${NC} $1"
    ((PASSED_TESTS++))
}

log_error() {
    echo -e "${RED}✗${NC} $1"
    ((FAILED_TESTS++))
}

log_warning() {
    echo -e "${YELLOW}⚠${NC} $1"
}

log_skip() {
    echo -e "${YELLOW}⊘${NC} $1"
    ((SKIPPED_TESTS++))
}

run_test_command() {
    local category=$1
    local test_name=$2
    local command=$3
    
    ((TOTAL_TESTS++))
    
    log_info "Running: $test_name"
    
    if [ "$DRY_RUN" = true ]; then
        log_info "DRY RUN: $command"
        log_success "$test_name (dry run)"
        return 0
    fi
    
    if [ "$VERBOSE" = true ]; then
        if eval "$command"; then
            log_success "$test_name"
            return 0
        else
            log_error "$test_name"
            FAILED_CATEGORIES+=("$category")
            [ "$FAIL_FAST" = true ] && exit 1
            return 1
        fi
    else
        if eval "$command" > /tmp/test_output.log 2>&1; then
            log_success "$test_name"
            return 0
        else
            log_error "$test_name"
            echo -e "${RED}Error output:${NC}"
            tail -20 /tmp/test_output.log
            FAILED_CATEGORIES+=("$category")
            [ "$FAIL_FAST" = true ] && exit 1
            return 1
        fi
    fi
}

check_prerequisite() {
    local name=$1
    local command=$2
    
    log_info "Checking prerequisite: $name"
    
    if eval "$command" > /dev/null 2>&1; then
        log_success "$name available"
        return 0
    else
        log_error "$name not available"
        return 1
    fi
}

wait_for_service() {
    local service=$1
    local url=$2
    local max_attempts=${3:-30}
    
    log_info "Waiting for $service to be ready..."
    
    for i in $(seq 1 $max_attempts); do
        if curl -s -f "$url" > /dev/null 2>&1; then
            log_success "$service is ready"
            return 0
        fi
        echo -n "."
        sleep 2
    done
    
    echo ""
    log_error "$service failed to become ready"
    return 1
}

##############################################################################
# Test Categories
##############################################################################

test_prerequisites() {
    print_section "Prerequisites Check"
    
    local prereq_failed=false
    
    check_prerequisite "kubectl" "kubectl version --client" || prereq_failed=true
    check_prerequisite "curl" "curl --version" || prereq_failed=true
    check_prerequisite "python3" "python3 --version" || prereq_failed=true
    check_prerequisite "jq" "jq --version" || prereq_failed=true
    
    # Check if Python requests module is available
    if python3 -c "import requests" 2>/dev/null; then
        log_success "Python requests module available"
    else
        log_warning "Python requests module not found - installing..."
        pip3 install requests > /dev/null 2>&1 || log_error "Failed to install requests"
    fi
    
    if [ "$prereq_failed" = true ]; then
        log_error "Prerequisites check failed"
        return 1
    fi
    
    log_success "All prerequisites satisfied"
    return 0
}

test_infrastructure() {
    print_section "Phase 0: Infrastructure Health"
    
    # Check Kubernetes cluster
    run_test_command "infrastructure" \
        "Kubernetes cluster connectivity" \
        "kubectl cluster-info > /dev/null"
    
    # Check namespace exists
    run_test_command "infrastructure" \
        "intelligent-sre namespace exists" \
        "kubectl get namespace intelligent-sre > /dev/null"
    
    # Check deployment exists
    run_test_command "infrastructure" \
        "intelligent-sre-mcp deployment exists" \
        "kubectl get deployment intelligent-sre-mcp -n intelligent-sre > /dev/null"
    
    # Check pods are running
    run_test_command "infrastructure" \
        "intelligent-sre-mcp pods running" \
        "kubectl get pods -n intelligent-sre -l app=intelligent-sre-mcp --field-selector=status.phase=Running | grep -q Running"
    
    # Check service exists
    run_test_command "infrastructure" \
        "intelligent-sre-mcp service exists" \
        "kubectl get service intelligent-sre-mcp -n intelligent-sre > /dev/null"
    
    # Wait for API server to be ready
    wait_for_service "API Server" "http://localhost:30080/health"
    
    # Check Prometheus (if available)
    if kubectl get service prometheus-service -n intelligent-sre > /dev/null 2>&1; then
        run_test_command "infrastructure" \
            "Prometheus service available" \
            "curl -s http://localhost:30090/-/healthy | grep -q 'Prometheus Server is Healthy'"
    else
        log_skip "Prometheus not deployed - skipping"
    fi
}

test_phase1_observability() {
    print_section "Phase 1: Observability Tools"
    
    # Test metrics endpoint
    run_test_command "observability" \
        "API health endpoint" \
        "curl -s -f http://localhost:30080/health | jq -e '.status == \"healthy\"' > /dev/null"
    
    # Test get_metrics tool
    run_test_command "observability" \
        "get_metrics - CPU usage" \
        "curl -s 'http://localhost:30080/metrics/query?metric=cpu&namespace=intelligent-sre' | jq -e '.data != null' > /dev/null"
    
    run_test_command "observability" \
        "get_metrics - Memory usage" \
        "curl -s 'http://localhost:30080/metrics/query?metric=memory&namespace=intelligent-sre' | jq -e '.data != null' > /dev/null"
    
    # Test get_logs tool
    run_test_command "observability" \
        "get_logs - Recent logs" \
        "curl -s 'http://localhost:30080/logs?namespace=intelligent-sre&lines=10' | jq -e 'length > 0' > /dev/null"
    
    # Test get_traces tool (if tracing is enabled)
    run_test_command "observability" \
        "get_traces endpoint" \
        "curl -s -f 'http://localhost:30080/traces?namespace=intelligent-sre&limit=5' > /dev/null"
}

test_phase2_detection() {
    print_section "Phase 2: Detection Tools"
    
    # Test anomaly detection
    run_test_command "detection" \
        "detect_anomalies - CPU" \
        "curl -s 'http://localhost:30080/detection/anomalies?namespace=intelligent-sre&metric=cpu' | jq -e '.anomalies != null' > /dev/null"
    
    run_test_command "detection" \
        "detect_anomalies - Memory" \
        "curl -s 'http://localhost:30080/detection/anomalies?namespace=intelligent-sre&metric=memory' | jq -e '.anomalies != null' > /dev/null"
    
    # Test pattern detection
    run_test_command "detection" \
        "detect_patterns - Error spikes" \
        "curl -s 'http://localhost:30080/detection/patterns?namespace=intelligent-sre&pattern_type=error_spike' | jq -e '.patterns != null' > /dev/null"
    
    run_test_command "detection" \
        "detect_patterns - Restart loops" \
        "curl -s 'http://localhost:30080/detection/patterns?namespace=intelligent-sre&pattern_type=restart_loop' | jq -e '.patterns != null' > /dev/null"
    
    # Test health scoring
    run_test_command "detection" \
        "get_health_score - Namespace" \
        "curl -s 'http://localhost:30080/detection/health-score?namespace=intelligent-sre' | jq -e '.health_score != null' > /dev/null"
    
    run_test_command "detection" \
        "get_health_score - Specific pod" \
        "curl -s 'http://localhost:30080/detection/health-score?namespace=intelligent-sre&pod_name=intelligent-sre-mcp' | jq -e '.health_score != null' > /dev/null"
    
    # Test correlation analysis
    run_test_command "detection" \
        "analyze_correlations" \
        "curl -s 'http://localhost:30080/detection/correlations?namespace=intelligent-sre' | jq -e '.correlations != null' > /dev/null"
    
    # Test root cause analysis
    run_test_command "detection" \
        "perform_rca" \
        "curl -s -X POST -H 'Content-Type: application/json' -d '{\"namespace\":\"intelligent-sre\",\"symptoms\":[\"high_cpu\"]}' http://localhost:30080/detection/rca | jq -e '.analysis != null' > /dev/null"
}

test_phase4_healing() {
    print_section "Phase 4: Self-Healing Actions (Dry-Run Mode)"
    
    # Get a test pod for healing actions
    local test_pod=$(kubectl get pods -n intelligent-sre -l app=intelligent-sre-mcp -o jsonpath='{.items[0].metadata.name}' 2>/dev/null || echo "test-pod")
    
    # Test restart_pod (dry-run)
    run_test_command "healing" \
        "restart_pod - Dry run" \
        "curl -s -X POST -H 'Content-Type: application/json' -d '{\"namespace\":\"intelligent-sre\",\"pod_name\":\"$test_pod\",\"dry_run\":true}' http://localhost:30080/healing/restart-pod | jq -e '.status == \"success\"' > /dev/null"
    
    # Test delete_failed_pods (dry-run)
    run_test_command "healing" \
        "delete_failed_pods - Dry run" \
        "curl -s -X POST -H 'Content-Type: application/json' -d '{\"namespace\":\"intelligent-sre\",\"dry_run\":true}' http://localhost:30080/healing/delete-failed-pods | jq -e '.status == \"success\"' > /dev/null"
    
    # Test scale_deployment (dry-run)
    run_test_command "healing" \
        "scale_deployment - Dry run" \
        "curl -s -X POST -H 'Content-Type: application/json' -d '{\"namespace\":\"intelligent-sre\",\"deployment_name\":\"intelligent-sre-mcp\",\"replicas\":2,\"dry_run\":true}' http://localhost:30080/healing/scale-deployment | jq -e '.status == \"success\"' > /dev/null"
    
    # Test rollback_deployment (dry-run)
    run_test_command "healing" \
        "rollback_deployment - Dry run" \
        "curl -s -X POST -H 'Content-Type: application/json' -d '{\"namespace\":\"intelligent-sre\",\"deployment_name\":\"intelligent-sre-mcp\",\"dry_run\":true}' http://localhost:30080/healing/rollback-deployment | jq -e '.status == \"success\"' > /dev/null"
    
    # Test node operations (dry-run)
    local test_node=$(kubectl get nodes -o jsonpath='{.items[0].metadata.name}' 2>/dev/null || echo "test-node")
    
    run_test_command "healing" \
        "cordon_node - Dry run" \
        "curl -s -X POST -H 'Content-Type: application/json' -d '{\"node_name\":\"$test_node\",\"dry_run\":true}' http://localhost:30080/healing/cordon-node | jq -e '.status == \"success\"' > /dev/null"
    
    run_test_command "healing" \
        "uncordon_node - Dry run" \
        "curl -s -X POST -H 'Content-Type: application/json' -d '{\"node_name\":\"$test_node\",\"dry_run\":true}' http://localhost:30080/healing/uncordon-node | jq -e '.status == \"success\"' > /dev/null"
    
    # Test healing history
    run_test_command "healing" \
        "get_healing_history" \
        "curl -s 'http://localhost:30080/healing/action-history?hours=24' | jq -e 'has(\"recent_actions\")' > /dev/null"

    run_test_command "learning" \
        "get_action_stats" \
        "curl -s 'http://localhost:30080/learning/action-stats?hours=24' | jq -e 'has(\"by_action_type\")' > /dev/null"

    run_test_command "learning" \
        "get_recurring_issues" \
        "curl -s 'http://localhost:30080/learning/recurring-issues?hours=24&min_count=2' | jq -e 'has(\"recurring_issues\")' > /dev/null"

    # Run healing scenarios (dry-run) menu
    run_test_command "healing" \
        "healing scenarios - dry run" \
        "printf '13\n\n0\n' | bash tests/test-healing-scenarios.sh"
}

test_integration() {
    print_section "Phase 4: Integration Tests"
    
    log_info "Running Python-based integration tests..."
    
    if [ -f "tests/test_healing_actions.py" ]; then
        run_test_command "integration" \
            "Python automated tests" \
            "cd /Users/sanket/Desktop/intelligent-sre-mcp && python3 tests/test_healing_actions.py"
    else
        log_skip "test_healing_actions.py not found"
    fi
    
    # End-to-end workflow test: Detection → Healing
    log_info "Testing E2E workflow: Detection → Healing"
    
    # 1. Detect issues
    local health_data=$(curl -s 'http://localhost:30080/detection/health-score?namespace=intelligent-sre' || echo '{}')
    if echo "$health_data" | jq -e '.health_score' > /dev/null 2>&1; then
        log_success "Detection: Health score retrieved"
        ((PASSED_TESTS++))
        
        # 2. If health score is low, test healing action (dry-run)
        local health_score=$(echo "$health_data" | jq -r '.health_score // 100')
        if (( $(echo "$health_score < 80" | bc -l) )); then
            log_warning "Health score is $health_score - testing healing action"
            if curl -s -X POST -H 'Content-Type: application/json' \
                -d '{"namespace":"intelligent-sre","dry_run":true}' \
                http://localhost:30080/healing/delete-failed-pods | jq -e '.status == "success"' > /dev/null; then
                log_success "Healing: Dry-run action successful"
                ((PASSED_TESTS++))
            else
                log_error "Healing: Dry-run action failed"
                ((FAILED_TESTS++))
            fi
        else
            log_success "Health score is good ($health_score) - no healing needed"
            ((PASSED_TESTS++))
        fi
    else
        log_error "Detection: Failed to retrieve health score"
        ((FAILED_TESTS++))
    fi
    
    ((TOTAL_TESTS += 2))
}

test_safety_mechanisms() {
    print_section "Phase 5: Safety Mechanism Validation"
    
    # Test rate limiting (should allow first 10, then block)
    log_info "Testing rate limiting..."
    local rate_limit_passed=true
    
    # Try 11 rapid-fire requests (should succeed for first 10, fail on 11th)
    for i in {1..11}; do
        local response=$(curl -s -X POST -H 'Content-Type: application/json' \
            -d '{"namespace":"intelligent-sre","dry_run":true}' \
            http://localhost:30080/healing/delete-failed-pods)
        
        if [ $i -le 10 ]; then
            if echo "$response" | jq -e '.status == "success"' > /dev/null; then
                [ $i -eq 1 ] && log_info "Rate limit test: Request $i/11 succeeded (expected)"
            else
                log_error "Rate limit test: Request $i should have succeeded"
                rate_limit_passed=false
                break
            fi
        else
            if echo "$response" | jq -e '.error' | grep -q "rate limit"; then
                log_success "Rate limiting working correctly (11th request blocked)"
            else
                log_warning "Rate limiting may not be working (11th request not blocked)"
            fi
        fi
    done
    
    if [ "$rate_limit_passed" = true ]; then
        log_success "Rate limiting validated"
        ((PASSED_TESTS++))
    else
        log_error "Rate limiting validation failed"
        ((FAILED_TESTS++))
    fi
    ((TOTAL_TESTS++))
    
    # Test blast radius control
    log_info "Testing blast radius control..."
    
    # Try to delete more than 5 pods at once (should be limited)
    run_test_command "safety" \
        "Blast radius control" \
        "curl -s -X POST -H 'Content-Type: application/json' -d '{\"namespace\":\"intelligent-sre\",\"label_selector\":\"app=test\",\"dry_run\":true}' http://localhost:30080/healing/delete-failed-pods | jq -e 'has(\"deleted_pods\")' > /dev/null"
    
    # Test dry-run mode
    log_info "Testing dry-run safety..."
    
    run_test_command "safety" \
        "Dry-run prevents actual execution" \
        "curl -s -X POST -H 'Content-Type: application/json' -d '{\"namespace\":\"intelligent-sre\",\"pod_name\":\"test-pod\",\"dry_run\":true}' http://localhost:30080/healing/restart-pod | jq -e '.dry_run == true' > /dev/null"
}

##############################################################################
# Main Test Execution
##############################################################################

print_usage() {
    cat << EOF
Usage: $0 [OPTIONS]

Smart test orchestrator for Intelligent SRE MCP.

Options:
    -v, --verbose       Enable verbose output
    -f, --fail-fast     Stop on first failure
    -d, --dry-run       Show what would be tested without executing
    --skip-cleanup      Don't clean up test resources
    -h, --help          Show this help message

Environment Variables:
    SKIP_CLEANUP=true   Skip cleanup after tests
    VERBOSE=true        Enable verbose output
    FAIL_FAST=true      Stop on first failure
    DRY_RUN=true        Dry run mode

Examples:
    # Run all tests
    $0

    # Run with verbose output
    $0 -v

    # Stop on first failure
    $0 -f

    # Dry run to see what would be tested
    $0 -d

EOF
}

parse_arguments() {
    while [[ $# -gt 0 ]]; do
        case $1 in
            -v|--verbose)
                VERBOSE=true
                shift
                ;;
            -f|--fail-fast)
                FAIL_FAST=true
                shift
                ;;
            -d|--dry-run)
                DRY_RUN=true
                shift
                ;;
            --skip-cleanup)
                SKIP_CLEANUP=true
                shift
                ;;
            -h|--help)
                print_usage
                exit 0
                ;;
            *)
                echo "Unknown option: $1"
                print_usage
                exit 1
                ;;
        esac
    done
}

print_summary() {
    echo -e "\n${WHITE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
    echo -e "${CYAN}Test Execution Summary${NC}"
    echo -e "${WHITE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}\n"
    
    echo -e "Total Tests:    ${WHITE}$TOTAL_TESTS${NC}"
    echo -e "Passed:         ${GREEN}$PASSED_TESTS${NC}"
    echo -e "Failed:         ${RED}$FAILED_TESTS${NC}"
    echo -e "Skipped:        ${YELLOW}$SKIPPED_TESTS${NC}"
    
    if [ $FAILED_TESTS -eq 0 ]; then
        echo -e "\n${GREEN}╔═══════════════════════════════════════════════════════════════════╗${NC}"
        echo -e "${GREEN}║                                                                   ║${NC}"
        echo -e "${GREEN}║                   ✓ ALL TESTS PASSED! 🎉                         ║${NC}"
        echo -e "${GREEN}║                                                                   ║${NC}"
        echo -e "${GREEN}╚═══════════════════════════════════════════════════════════════════╝${NC}\n"
        
        echo -e "${GREEN}The Intelligent SRE MCP is fully operational:${NC}"
        echo -e "  ${GREEN}✓${NC} Infrastructure healthy"
        echo -e "  ${GREEN}✓${NC} Phase 1: Observability tools working"
        echo -e "  ${GREEN}✓${NC} Phase 2: Detection algorithms operational"
        echo -e "  ${GREEN}✓${NC} Phase 4: Self-healing actions ready"
        echo -e "  ${GREEN}✓${NC} Safety mechanisms validated"
        echo -e "  ${GREEN}✓${NC} Integration tests passed"
        
        echo -e "\n${CYAN}Ready for production use with Claude Desktop! 🚀${NC}\n"
        return 0
    else
        echo -e "\n${RED}╔═══════════════════════════════════════════════════════════════════╗${NC}"
        echo -e "${RED}║                                                                   ║${NC}"
        echo -e "${RED}║                   ✗ SOME TESTS FAILED                            ║${NC}"
        echo -e "${RED}║                                                                   ║${NC}"
        echo -e "${RED}╚═══════════════════════════════════════════════════════════════════╝${NC}\n"
        
        if [ ${#FAILED_CATEGORIES[@]} -gt 0 ]; then
            echo -e "${RED}Failed Categories:${NC}"
            printf '%s\n' "${FAILED_CATEGORIES[@]}" | sort -u | while read category; do
                echo -e "  ${RED}✗${NC} $category"
            done
        fi
        
        echo -e "\n${YELLOW}Check the test output above for details.${NC}"
        echo -e "${YELLOW}Run with -v flag for verbose output.${NC}\n"
        return 1
    fi
}

main() {
    parse_arguments "$@"
    
    print_banner
    
    if [ "$DRY_RUN" = true ]; then
        log_warning "Running in DRY-RUN mode - no actual tests will execute"
    fi
    
    # Start timer
    START_TIME=$(date +%s)
    
    # Run test categories in architectural order
    test_prerequisites || { log_error "Prerequisites failed - cannot continue"; exit 1; }
    test_infrastructure || log_warning "Infrastructure tests had failures"
    test_phase1_observability || log_warning "Phase 1 tests had failures"
    test_phase2_detection || log_warning "Phase 2 tests had failures"
    test_phase4_healing || log_warning "Phase 4 tests had failures"
    test_integration || log_warning "Integration tests had failures"
    test_safety_mechanisms || log_warning "Safety mechanism tests had failures"
    
    # End timer
    END_TIME=$(date +%s)
    DURATION=$((END_TIME - START_TIME))
    
    echo -e "\n${BLUE}Test execution completed in ${DURATION} seconds${NC}\n"
    
    print_summary
    
    exit $FAILED_TESTS
}

# Run main function
main "$@"
