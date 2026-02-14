#!/bin/bash
# Quick test runner for Intelligent SRE MCP

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

# Banner
echo ""
echo -e "${CYAN}${BOLD}╔════════════════════════════════════════════════════╗${NC}"
echo -e "${CYAN}${BOLD}║   Intelligent SRE MCP - Test Runner               ║${NC}"
echo -e "${CYAN}${BOLD}╚════════════════════════════════════════════════════╝${NC}"
echo ""

# Check if tests directory exists
if [ ! -d "tests" ]; then
    echo -e "${RED}Error: tests/ directory not found${NC}"
    exit 1
fi

# Show options
echo -e "${BOLD}Available Tests:${NC}"
echo ""
echo -e "${MAGENTA}${BOLD}1. 🚀 End-to-End Test with Claude Desktop (Recommended)${NC}"
echo -e "   ${CYAN}→ Deploys test infrastructure, detects issues, test with Claude${NC}"
echo -e "   ${CYAN}→ Duration: ~5-10 min + your testing time${NC}"
echo -e "   ${CYAN}→ Perfect for: Demos, validation, Claude integration${NC}"
echo ""
echo -e "${BLUE}2. 📋 Automated Test Suite (Quick)${NC}"
echo -e "   ${CYAN}→ Runs 10 automated tests${NC}"
echo -e "   ${CYAN}→ Duration: ~30 seconds${NC}"
echo -e "   ${CYAN}→ Perfect for: CI/CD, quick validation${NC}"
echo ""
echo -e "${BLUE}3. 🎯 Interactive Test Scenarios (Menu)${NC}"
echo -e "   ${CYAN}→ Choose from 11 different scenarios${NC}"
echo -e "   ${CYAN}→ Duration: Varies by scenario${NC}"
echo -e "   ${CYAN}→ Perfect for: Testing specific issues${NC}"
echo ""
echo -e "${YELLOW}4. 🔄 Run Automated Tests + Scenarios${NC}"
echo -e "   ${CYAN}→ Runs automated tests, then shows scenario menu${NC}"
echo ""
echo -e "${GREEN}0. Exit${NC}"
echo ""
echo -ne "${BOLD}Enter choice (0-4): ${NC}"
read choice

case $choice in
    1)
        echo ""
        echo -e "${MAGENTA}${BOLD}🚀 Launching End-to-End Test...${NC}"
        echo ""
        ./tests/test-e2e-with-claude.sh
        ;;
    2)
        echo ""
        echo -e "${BLUE}${BOLD}📋 Running Automated Test Suite...${NC}"
        echo ""
        python3 tests/test_detection.py
        echo ""
        echo -e "${GREEN}${BOLD}✓ Automated tests complete!${NC}"
        ;;
    3)
        echo ""
        echo -e "${BLUE}${BOLD}🎯 Starting Interactive Test Scenarios...${NC}"
        echo ""
        ./tests/test-scenarios.sh
        ;;
    4)
        echo ""
        echo -e "${YELLOW}${BOLD}🔄 Running Full Test Suite...${NC}"
        echo ""
        echo -e "${BLUE}Phase 1: Automated Tests${NC}"
        python3 tests/test_detection.py
        
        echo ""
        echo -e "${GREEN}${BOLD}✓ Automated tests complete!${NC}"
        echo ""
        echo -e "${YELLOW}Press Enter to continue to interactive scenarios...${NC}"
        read
        
        echo ""
        echo -e "${BLUE}Phase 2: Interactive Scenarios${NC}"
        ./tests/test-scenarios.sh
        ;;
    0)
        echo ""
        echo -e "${GREEN}Goodbye!${NC}"
        exit 0
        ;;
    *)
        echo ""
        echo -e "${RED}Invalid choice. Please run again and select 0-4.${NC}"
        exit 1
        ;;
esac

echo ""
echo -e "${GREEN}${BOLD}════════════════════════════════════════${NC}"
echo -e "${GREEN}${BOLD}Testing Complete! 🎉${NC}"
echo -e "${GREEN}${BOLD}════════════════════════════════════════${NC}"
echo ""
