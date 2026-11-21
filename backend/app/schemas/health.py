from pydantic import BaseModel


class HealthResponse(BaseModel):
    status: str
    app_name: str
    llm_provider: str
    llm_configured: bool  # True if an API key is present. The key itself is never returned.
