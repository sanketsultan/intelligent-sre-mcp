import os
import httpx
from mcp.server.fastmcp import FastMCP

# API endpoint (Kubernetes NodePort)
API_URL = os.getenv("API_URL", "http://localhost:30080").rstrip("/")
TIMEOUT = float(os.getenv("REQUEST_TIMEOUT", "10"))

mcp = FastMCP("intelligent-sre-mcp-client")

@mcp.tool()
def prom_query(query: str) -> str:
    """
    Run a PromQL instant query against Prometheus via the Kubernetes API and return the JSON response.
    Example query: up
    """
    try:
        with httpx.Client(timeout=TIMEOUT) as client:
            response = client.post(
                f"{API_URL}/query",
                json={"query": query},
                headers={"Content-Type": "application/json"}
            )
            response.raise_for_status()
            return str(response.json())
    except httpx.HTTPError as e:
        return f"Error querying API: {str(e)}"

@mcp.tool()
def get_targets() -> str:
    """
    Get all Prometheus targets and their status.
    """
    try:
        with httpx.Client(timeout=TIMEOUT) as client:
            response = client.get(f"{API_URL}/targets")
            response.raise_for_status()
            return str(response.json())
    except httpx.HTTPError as e:
        return f"Error getting targets: {str(e)}"

@mcp.tool()
def health_check() -> str:
    """
    Check the health of the monitoring API.
    """
    try:
        with httpx.Client(timeout=TIMEOUT) as client:
            response = client.get(f"{API_URL}/health")
            response.raise_for_status()
            return str(response.json())
    except httpx.HTTPError as e:
        return f"Error checking health: {str(e)}"

def main():
    # IMPORTANT: do not print to stdout in stdio servers
    mcp.run(transport="stdio")

if __name__ == "__main__":
    main()
