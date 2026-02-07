from pydantic import BaseModel
import os

class Settings(BaseModel):
    prometheus_url: str = "http://localhost:9090"
    request_timeout: int = 10  # seconds

def load_settings() -> Settings:
    return Settings(
        prometheus_url=os.getenv("PROMETHEUS_URL", "http://localhost:9090"),
        request_timeout=int(os.getenv("REQUEST_TIMEOUT", "10")),
    )
