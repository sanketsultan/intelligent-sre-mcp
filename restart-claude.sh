#!/bin/bash

##############################################################################
# Claude Desktop Restart & Verification Script
# 
# This script restarts Claude Desktop and verifies MCP tools are loaded
##############################################################################

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
NC='\033[0m'
BOLD='\033[1m'

echo -e "${CYAN}"
cat << 'EOF'
╔═══════════════════════════════════════════════════════════════════╗
║                                                                   ║
║           🔄 CLAUDE DESKTOP RESTART & VERIFICATION 🔄            ║
║                                                                   ║
╚═══════════════════════════════════════════════════════════════════╝
EOF
echo -e "${NC}\n"

# Step 1: Check if API server is running
echo -e "${CYAN}[1/5] Checking API server...${NC}"
if curl -s -f http://localhost:30080/health > /dev/null 2>&1; then
    echo -e "${GREEN}✓ API server is running${NC}\n"
else
    echo -e "${RED}✗ API server is not running!${NC}"
    echo -e "${YELLOW}Start it with: kubectl get pods -n intelligent-sre${NC}\n"
    exit 1
fi

# Step 2: Check MCP configuration
echo -e "${CYAN}[2/5] Checking MCP configuration...${NC}"
CONFIG_FILE="$HOME/Library/Application Support/Claude/claude_desktop_config.json"

if [ -f "$CONFIG_FILE" ]; then
    echo -e "${GREEN}✓ Config file exists${NC}"
    
    if grep -q "intelligent-sre-mcp" "$CONFIG_FILE"; then
        echo -e "${GREEN}✓ intelligent-sre-mcp is configured${NC}"
    else
        echo -e "${RED}✗ intelligent-sre-mcp not found in config${NC}"
        exit 1
    fi
    
    if grep -q "run_mcp_api.sh" "$CONFIG_FILE"; then
        echo -e "${GREEN}✓ MCP script path is configured${NC}"
    else
        echo -e "${YELLOW}⚠ MCP script path may be incorrect${NC}"
    fi
else
    echo -e "${RED}✗ Config file not found!${NC}"
    exit 1
fi
echo ""

# Step 3: Check MCP script
echo -e "${CYAN}[3/5] Checking MCP script...${NC}"
MCP_SCRIPT="/Users/$(whoami)/Desktop/intelligent-sre-mcp/run_mcp_api.sh"

if [ -f "$MCP_SCRIPT" ]; then
    echo -e "${GREEN}✓ MCP script exists${NC}"
    
    if [ -x "$MCP_SCRIPT" ]; then
        echo -e "${GREEN}✓ MCP script is executable${NC}"
    else
        echo -e "${YELLOW}⚠ Making MCP script executable...${NC}"
        chmod +x "$MCP_SCRIPT"
        echo -e "${GREEN}✓ Fixed${NC}"
    fi
else
    echo -e "${RED}✗ MCP script not found at: $MCP_SCRIPT${NC}"
    exit 1
fi
echo ""

# Step 4: Kill existing Claude processes
echo -e "${CYAN}[4/5] Restarting Claude Desktop...${NC}"

CLAUDE_PIDS=$(pgrep -i claude 2>/dev/null || echo "")

if [ -n "$CLAUDE_PIDS" ]; then
    echo -e "${YELLOW}Stopping existing Claude processes...${NC}"
    killall Claude 2>/dev/null || killall claude 2>/dev/null || true
    sleep 2
    echo -e "${GREEN}✓ Claude stopped${NC}"
else
    echo -e "${YELLOW}Claude was not running${NC}"
fi

echo -e "${GREEN}Starting Claude Desktop...${NC}"
open -a Claude

echo -e "${YELLOW}Waiting for Claude to start (5 seconds)...${NC}"
sleep 5

if pgrep -i claude > /dev/null 2>&1; then
    echo -e "${GREEN}✓ Claude Desktop is running${NC}"
else
    echo -e "${RED}✗ Claude failed to start${NC}"
    exit 1
fi
echo ""

# Step 5: Show verification instructions
echo -e "${CYAN}[5/5] Verification Instructions${NC}\n"

echo -e "${BOLD}${GREEN}✅ Claude Desktop has been restarted!${NC}\n"

echo -e "${BOLD}To verify the healing tools are loaded:${NC}\n"

echo -e "${YELLOW}1. Open Claude Desktop and type:${NC}"
echo '   "What tools do you have access to?"'
echo ""

echo -e "${YELLOW}2. Look for these Phase 3 healing tools:${NC}"
echo "   • restart_pod"
echo "   • delete_failed_pods"
echo "   • scale_deployment"
echo "   • rollback_deployment"
echo "   • cordon_node"
echo "   • uncordon_node"
echo "   • get_healing_history"
echo ""

echo -e "${YELLOW}3. Test a healing action (dry-run):${NC}"
echo '   "Delete all failed pods in intelligent-sre namespace using dry_run=true"'
echo ""

echo -e "${CYAN}Expected MCP Tools:${NC}"
echo "  Phase 1: Observability (3 tools)"
echo "  Phase 2: Detection (6 tools)"
echo "  Phase 3: Self-Healing (7 tools) ← NEW!"
echo "  Kubernetes Ops (8 tools)"
echo "  ${BOLD}Total: 24 tools${NC}"
echo ""

echo -e "${GREEN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo -e "${GREEN}${BOLD}If Claude doesn't show healing tools, check the logs:${NC}"
echo -e "${CYAN}~/Library/Logs/Claude/mcp*.log${NC}"
echo -e "${GREEN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo ""

echo -e "${BOLD}${CYAN}Test healing actions with these prompts:${NC}"
echo '  • "Show me healing action history"'
echo '  • "What is the health score of intelligent-sre namespace?"'
echo '  • "Delete failed pods (dry run first)"'
echo '  • "Scale test-app deployment to 2 replicas (dry run)"'
echo ""

echo -e "${GREEN}${BOLD}Claude Desktop is ready! 🤖${NC}\n"
