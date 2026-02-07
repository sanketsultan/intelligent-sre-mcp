# intelligent-sre-mcp
A smart SRE platform that combines monitoring, context, and AI to detect incidents, analyze root causes, and assist with auto-healing.

An intelligent SRE copilot that lets you ask questions about your infrastructure
in plain English and get answers directly from Prometheus using Claude Desktop
via the Model Context Protocol (MCP).

Think of it as:
“Claude, but connected to my monitoring system.”


WHAT THIS PROJECT DOES
---------------------
This project creates a Python-based MCP server that:
- Connects to Prometheus
- Exposes Prometheus data as tools to Claude Desktop
- Lets you ask things like:
  - Is my system healthy?
  - Which targets are down?
  - What’s the CPU usage right now?

Claude does not guess. It queries real metrics.


ARCHITECTURE (SIMPLE)
---------------------
Claude Desktop
    |
    | (MCP over stdio)
    v
intelligent-sre-mcp (Python MCP server)
    |
    | (HTTP / PromQL)
    v
Prometheus (Docker, local)
    |
    v
node-exporter (machine metrics)


PREREQUISITES
-------------
- macOS or Linux
- Python 3.10+
- Docker + Docker Compose
- Claude Desktop (app)


STEP 1: CLONE THE REPO
---------------------
git clone https://github.com/sanketsultan/intelligent-sre-mcp.git
cd intelligent-sre-mcp


STEP 2: PYTHON VIRTUAL ENVIRONMENT
---------------------------------
python3 -m venv .venv
source .venv/bin/activate

Upgrade tools:
pip install -U pip setuptools wheel

Install dependencies:
pip install -U "mcp[cli]" httpx


STEP 3: START PROMETHEUS 
---------------------------------------
cd infra
docker compose up -d

Prometheus UI:
http://localhost:9090

Verify:
curl http://localhost:9090/api/v1/query?query=up | python -m json.tool

If empty:
docker compose restart prometheus


STEP 4: MCP SERVER (PYTHON)
--------------------------
The MCP server lives in:
src/intelligent_sre_mcp/server.py

Rules:
- NEVER print to stdout
- Use FastMCP
- Prometheus queried via HTTP


STEP 5: WRAPPER SCRIPT (IMPORTANT)
---------------------------------
Create run_mcp.sh in repo root:

#!/usr/bin/env bash
set -euo pipefail

export PROMETHEUS_URL="http://localhost:9090"
export PYTHONPATH="$(cd "$(dirname "$0")" && pwd)/src"

exec "$(cd "$(dirname "$0")" && pwd)/.venv/bin/python" -m intelligent_sre_mcp.server

Make executable:
chmod +x run_mcp.sh

Test:
./run_mcp.sh
(it should hang – that is correct)


STEP 6: CONNECT CLAUDE DESKTOP
-----------------------------
Create/edit:
~/Library/Application Support/Claude/claude_desktop_config.json

{
  "mcpServers": {
    "intelligent-sre-mcp": {
      "command": "/Users/YOUR_USERNAME/Desktop/intelligent-sre-mcp/run_mcp.sh",
      "args": [],
      "env": {}
    }
  }
}

Use absolute paths.


STEP 7: RESTART CLAUDE
---------------------
Quit Claude completely (Cmd+Q)
Open Claude Desktop again


STEP 8: PROMPTS TO USE IN CLAUDE
-------------------------------

Basic checks:
Run prom_query with query "up"
Run prom_query with query "prometheus_build_info"

Health checks:
Run prom_query with query "up == 0"
Run prom_query with query "count(up == 1)"
Run prom_query with query "avg(up)"

System metrics:
Run prom_query with query "rate(node_cpu_seconds_total{mode!='idle'}[5m])"
Run prom_query with query "node_memory_MemAvailable_bytes"
Run prom_query with query "node_filesystem_avail_bytes"

