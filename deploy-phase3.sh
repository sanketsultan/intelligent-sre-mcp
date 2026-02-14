#!/bin/bash

##############################################################################
# Phase 3 Deployment Script
# 
# Deploys the new Phase 3 self-healing capabilities to the cluster
##############################################################################

set -e

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
NC='\033[0m'

echo -e "${CYAN}"
cat << 'EOF'
╔═══════════════════════════════════════════════════════════════════╗
║                                                                   ║
║              🚀 PHASE 3 DEPLOYMENT SCRIPT 🚀                     ║
║                                                                   ║
║           Deploying Self-Healing Capabilities                     ║
║                                                                   ║
╚═══════════════════════════════════════════════════════════════════╝
EOF
echo -e "${NC}\n"

# Step 1: Build Docker image
echo -e "${CYAN}[1/5] Building Docker image...${NC}"
if docker build -t intelligent-sre-mcp:latest .; then
    echo -e "${GREEN}✓ Docker image built successfully${NC}\n"
else
    echo -e "${RED}✗ Failed to build Docker image${NC}"
    exit 1
fi

# Step 2: Load image into kind (if using kind)
if kubectl get nodes | grep -q "kind"; then
    echo -e "${CYAN}[2/5] Loading image into kind cluster...${NC}"
    if kind load docker-image intelligent-sre-mcp:latest; then
        echo -e "${GREEN}✓ Image loaded into kind cluster${NC}\n"
    else
        echo -e "${YELLOW}⚠ Failed to load image into kind (might not be using kind)${NC}\n"
    fi
else
    echo -e "${YELLOW}[2/5] Not using kind cluster - skipping image load${NC}\n"
fi

# Step 3: Restart deployment
echo -e "${CYAN}[3/5] Restarting deployment...${NC}"
if kubectl rollout restart deployment/intelligent-sre-mcp -n intelligent-sre; then
    echo -e "${GREEN}✓ Deployment restart initiated${NC}\n"
else
    echo -e "${RED}✗ Failed to restart deployment${NC}"
    exit 1
fi

# Step 4: Wait for rollout
echo -e "${CYAN}[4/5] Waiting for rollout to complete...${NC}"
if kubectl rollout status deployment/intelligent-sre-mcp -n intelligent-sre --timeout=120s; then
    echo -e "${GREEN}✓ Rollout completed successfully${NC}\n"
else
    echo -e "${RED}✗ Rollout failed or timed out${NC}"
    exit 1
fi

# Step 5: Verify deployment
echo -e "${CYAN}[5/5] Verifying deployment...${NC}"

# Check pods are running
if kubectl get pods -n intelligent-sre -l app=intelligent-sre-mcp --field-selector=status.phase=Running | grep -q "Running"; then
    echo -e "${GREEN}✓ Pods are running${NC}"
else
    echo -e "${RED}✗ Pods are not running${NC}"
    kubectl get pods -n intelligent-sre -l app=intelligent-sre-mcp
    exit 1
fi

# Wait for API to be ready
echo -e "\n${CYAN}Waiting for API server to be ready...${NC}"
for i in {1..30}; do
    if curl -s -f http://localhost:30080/health > /dev/null 2>&1; then
        echo -e "${GREEN}✓ API server is ready${NC}"
        break
    fi
    echo -n "."
    sleep 2
done

# Verify Phase 3 endpoints
echo -e "\n${CYAN}Verifying Phase 3 endpoints...${NC}"

# Test healing history endpoint
if curl -s -f http://localhost:30080/healing/action-history > /dev/null 2>&1; then
    echo -e "${GREEN}✓ Healing action history endpoint available${NC}"
else
    echo -e "${RED}✗ Healing action history endpoint not available${NC}"
    echo -e "${YELLOW}Checking logs:${NC}"
    kubectl logs -n intelligent-sre deployment/intelligent-sre-mcp --tail=20
    exit 1
fi

# Show current status
echo -e "\n${CYAN}Current deployment status:${NC}"
kubectl get pods -n intelligent-sre -l app=intelligent-sre-mcp

echo -e "\n${CYAN}Recent logs:${NC}"
kubectl logs -n intelligent-sre deployment/intelligent-sre-mcp --tail=10

echo -e "\n${GREEN}╔═══════════════════════════════════════════════════════════════════╗${NC}"
echo -e "${GREEN}║                                                                   ║${NC}"
echo -e "${GREEN}║              ✓ PHASE 3 DEPLOYED SUCCESSFULLY! 🎉                 ║${NC}"
echo -e "${GREEN}║                                                                   ║${NC}"
echo -e "${GREEN}╚═══════════════════════════════════════════════════════════════════╝${NC}\n"

echo -e "${CYAN}Next steps:${NC}"
echo -e "1. Run tests: ${YELLOW}./tests/run-all-tests.sh${NC}"
echo -e "2. Restart Claude Desktop to load new tools"
echo -e "3. Try self-healing actions with Claude!\n"

echo -e "${GREEN}The system is now ready with all 24 MCP tools! 🚀${NC}\n"
