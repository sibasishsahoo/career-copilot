"""Pydantic schemas for the agent."""

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

MAX_QUESTION_CHARS = 500


# ---------- what the LLM must return on every turn ----------

class AgentDecision(BaseModel):
    """One turn of the agent: either call a tool or give the final answer."""

    model_config = ConfigDict(str_strip_whitespace=True)

    thought: str | None = Field(default=None, max_length=1000)
    action: Literal["tool", "final"]
    tool: str | None = None
    arguments: dict[str, Any] | None = None  # models often send null here on a final answer
    answer: str | None = None

    @model_validator(mode="after")
    def fields_must_match_the_action(self) -> "AgentDecision":
        # The retry message the model sees quotes these, so write them for the model to read.
        if self.action == "tool" and not self.tool:
            raise ValueError('"tool" is required when action is "tool"')
        if self.action == "final" and not self.answer:
            raise ValueError('"answer" is required when action is "final"')
        return self


# ---------- API ----------

class AgentAskRequest(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")

    question: str = Field(min_length=1, max_length=MAX_QUESTION_CHARS)


class AgentStepRead(BaseModel):
    number: int
    thought: str | None  # the model's own explanation: useful to read, but not guaranteed to be faithful
    tool: str
    arguments: dict[str, Any]
    observation: str  # exactly what the model was shown as the result
    ok: bool


class AgentAskResponse(BaseModel):
    question: str
    answer: str
    stopped_reason: Literal["final", "max_steps"]
    steps: list[AgentStepRead]  # the full trace
