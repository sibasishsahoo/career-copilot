"""Plain data classes for the agent (no third-party packages)."""

from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class Decision:
    """What the model decided on one turn: call a tool, or give the final answer."""

    action: str  # "tool" or "final"
    thought: str | None = None  # the model's own one-line explanation (shown in the trace)
    tool: str | None = None
    arguments: dict[str, Any] = field(default_factory=dict)
    answer: str | None = None


@dataclass(frozen=True)
class AgentStep:
    """One completed tool call, as recorded in the trace."""

    number: int
    thought: str | None
    tool: str
    arguments: dict[str, Any]
    observation: str  # the text the model was shown as the tool's result
    ok: bool  # False when the call failed (bad arguments, unknown tool, tool error)


@dataclass(frozen=True)
class AgentResult:
    answer: str
    steps: list[AgentStep]
    stopped_reason: str  # "final" = the model answered, "max_steps" = we ran out of steps
