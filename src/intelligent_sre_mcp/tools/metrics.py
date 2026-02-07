import httpx
from typing import Dict, Any

class PrometheusClient:
    def __init__(self, base_url: str, timeout: int = 10):
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout

    def query(self, query: str) -> Dict[str, Any]:
        url = f"{self.base_url}/api/v1/query"
        with httpx.Client(timeout=self.timeout) as client:
            r = client.get(url, params={"query": query})
            r.raise_for_status()
            return r.json()
