#!/bin/bash
# Quick setup script for Claude Desktop configuration

CONFIG_FILE="$HOME/Library/Application Support/Claude/claude_desktop_config.json"
PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

echo "🔧 Updating Claude Desktop configuration..."

# Backup existing config
if [ -f "$CONFIG_FILE" ]; then
    cp "$CONFIG_FILE" "$CONFIG_FILE.backup.$(date +%Y%m%d_%H%M%S)"
    echo "Backed up existing config"
fi

# Create config directory if it doesn't exist
mkdir -p "$(dirname "$CONFIG_FILE")"

# Write new config
cat > "$CONFIG_FILE" << EOF
{
  "mcpServers": {
    "intelligent-sre-mcp": {
      "command": "$PROJECT_DIR/setup/run_mcp_api.sh",
      "args": [],
      "env": {
        "API_URL": "http://localhost:30080"
      }
    }
  }
}
EOF

echo "✅ Updated Claude Desktop configuration"
echo ""
echo "📋 Configuration written to:"
echo "   $CONFIG_FILE"
echo ""
echo "🔄 Next steps:"
echo "   1. Restart Claude Desktop (Cmd+Q, then reopen)"
echo "   2. Verify Kubernetes is running: kubectl get pods -n intelligent-sre"
echo "   3. Test in Claude: 'Run health_check tool'"
echo ""
echo "🎯 Available tools in Claude:"
echo "   - prom_query: Run PromQL queries"
echo "   - get_targets: Get Prometheus targets"
echo "   - health_check: Check API health"
echo ""
