from pydantic import BaseModel, Field


class LLMTestRequest(BaseModel):
    # Pydantic rejects empty or oversized prompts automatically (HTTP 422).
    prompt: str = Field(min_length=1, max_length=2000)


class LLMTestResponse(BaseModel):
    provider: str
    model: str
    reply: str
