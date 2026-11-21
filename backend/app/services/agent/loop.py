"""The agent loop - the whole idea of an "agent" in about 40 lines.

    repeat (at most max_steps times):
        1. show the model the question + everything that happened so far
        2. the model replies with a Decision: call a tool, or give the final answer
        3. if it called a tool: run it (safely) and record the result, then go back to 1

This file contains no LLM code and no JSON parsing. It receives a `decide` function; in production
that function asks the LLM (see decider.py), and in tests it is a script of prepared decisions. So
the loop's behaviour - guards, error handling, step limit - can be tested exactly, with no AI involved.
"""

import json
from collections.abc import Callable

from app.services.agent.models import AgentResult, AgentStep, Decision
from app.services.agent.prompts import build_system_prompt, build_turn_prompt
from app.services.agent.tools import ToolOutcome, ToolRegistry, execute_tool

# decide(system_prompt, turn_prompt) -> Decision
Decider = Callable[[str, str], Decision]

HARD_MAX_STEPS = 10  # whatever the settings say, the loop can never run longer than this
GAVE_UP_ANSWER = (
    "I couldn't finish this within {n} steps. The steps in the trace show what I found so far."
)
NO_ANSWER = "I'm sorry, I could not produce an answer."


def run_agent(decide: Decider, registry: ToolRegistry, question: str, max_steps: int = 4) -> AgentResult:
    max_steps = max(1, min(max_steps, HARD_MAX_STEPS))
    system_prompt = build_system_prompt(registry)
    steps: list[AgentStep] = []
    seen_calls: set[tuple[str, str]] = set()

    for number in range(1, max_steps + 1):
        last_step = number == max_steps
        decision = decide(system_prompt, build_turn_prompt(question, steps, last_step))

        if decision.action == "final":
            return AgentResult((decision.answer or "").strip() or NO_ANSWER, steps, "final")

        tool_name = decision.tool or ""
        arguments = decision.arguments or {}

        # Guard against loops: the same call twice would give the same result and waste a step.
        call_key = (tool_name, json.dumps(arguments, sort_keys=True, default=str))
        if call_key in seen_calls:
            outcome = ToolOutcome(
                "Error: you already made this exact call; its result is in an earlier step. "
                "Use that result, try different arguments, or give your final answer.",
                False,
            )
        else:
            seen_calls.add(call_key)
            outcome = execute_tool(registry, tool_name, arguments)

        steps.append(AgentStep(number, decision.thought, tool_name, arguments, outcome.observation, outcome.ok))

    return AgentResult(GAVE_UP_ANSWER.format(n=max_steps), steps, "max_steps")
