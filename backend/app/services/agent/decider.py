"""The bridge between the loop and the LLM: ask the model for its next Decision.

Reuses generate_structured from Phase 2, unchanged: it asks the model for JSON, extracts it,
validates it against AgentDecision, and retries once with the exact problem if the reply was
malformed, had a missing field or a wrong type.
"""

from app.schemas.agent import AgentDecision
from app.services.agent.models import Decision
from app.services.llm.base import LLMClient
from app.services.llm.structured import generate_structured


class LLMDecider:
    def __init__(self, llm: LLMClient, max_retries: int = 1) -> None:
        self._llm = llm
        self._max_retries = max_retries

    def __call__(self, system_prompt: str, turn_prompt: str) -> Decision:
        parsed = generate_structured(
            llm=self._llm,
            prompt=turn_prompt,
            schema=AgentDecision,
            system_prompt=system_prompt,
            max_retries=self._max_retries,
        )
        return Decision(
            action=parsed.action,
            thought=parsed.thought,
            tool=parsed.tool,
            arguments=dict(parsed.arguments or {}),
            answer=parsed.answer,
        )
