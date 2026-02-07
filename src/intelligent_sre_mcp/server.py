import os
import httpx
from mcp.server.fastmcp import FastMCP

PROM_URL = os.getenv("PROMETHEUS_URL", "http://localhost:9090").rstrip("/")
TIMEOUT = float(os.getenv("REQUEST_TIMEOUT", "10"))

mcp = FastMCP("intelligent-sre-mcp")


def prom_query_instant(query: str) -> dict:
    url = f"{PROM_URL}/api/v1/query"
    with httpx.Client(timeout=TIMEOUT) as client:
        r = client.get(url, params={"query": query})
        r.raise_for_status()
        return r.json()


@mcp.tool()
def prom_query(query: str) -> str:
    """
    Run a PromQL instant query against Prometheus and return the JSON response.
    Example query: up
    """
    data = prom_query_instant(query)
    return str(data)


def main():
    # IMPORTANT: do not print to stdout in stdio servers
    mcp.run(transport="stdio")


if __name__ == "__main__":
    main()
