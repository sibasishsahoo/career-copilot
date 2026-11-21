import pytest

from app.services.agent.loop import GAVE_UP_ANSWER, HARD_MAX_STEPS, NO_ANSWER, run_agent
from app.services.agent.models import Decision
from app.services.agent.tools import Tool, ToolError, ToolParam, ToolRegistry


class ScriptedDecider:
    """Plays the model: hands back prepared decisions one by one and records every prompt it was shown."""

    def __init__(self, decisions):
        self.decisions = list(decisions)
        self.system_prompts: list[str] = []
        self.turn_prompts: list[str] = []

    def __call__(self, system_prompt, turn_prompt):
        self.system_prompts.append(system_prompt)
        self.turn_prompts.append(turn_prompt)
        if not self.decisions:
            raise AssertionError("the agent asked for more decisions than were scripted")
        item = self.decisions.pop(0)
        if isinstance(item, Exception):
            raise item
        return item


def call(tool, thought=None, **arguments):
    return Decision(action="tool", thought=thought, tool=tool, arguments=arguments)


def final(answer, thought=None):
    return Decision(action="final", thought=thought, answer=answer)


def make_registry(calls=None):
    calls = calls if calls is not None else []

    def lookup(args):
        calls.append(("lookup", args))
        return {"found": args["name"]}

    def broken(args):
        raise ToolError("Application 9 was not found.")

    def count(args):
        calls.append(("count", args))
        return {"n": args["limit"]}

    return ToolRegistry(
        [
            Tool("lookup", "Look a name up.", (ToolParam("name", "string", "the name"),), lookup),
            Tool("broken", "Always fails.", (), broken),
            Tool("count", "Count.", (ToolParam("limit", "integer", "n", required=False, default=5),), count),
        ]
    )


# ======================= the happy paths =======================

def test_the_model_can_answer_without_any_tool():
    decider = ScriptedDecider([final("Hello!")])
    result = run_agent(decider, make_registry(), "Say hi")
    assert result.answer == "Hello!"
    assert result.stopped_reason == "final"
    assert result.steps == []
    assert len(decider.turn_prompts) == 1


def test_a_tool_call_then_a_final_answer():
    decider = ScriptedDecider([call("lookup", "Need the record.", name="Acme"), final("It is Acme.")])
    result = run_agent(decider, make_registry(), "Who?")

    assert result.answer == "It is Acme." and result.stopped_reason == "final"
    assert len(result.steps) == 1
    step = result.steps[0]
    assert (step.number, step.thought, step.tool, step.arguments, step.ok) == (
        1, "Need the record.", "lookup", {"name": "Acme"}, True,
    )
    assert step.observation == '{"found":"Acme"}'


def test_the_observation_is_shown_to_the_model_on_the_next_turn():
    decider = ScriptedDecider([call("lookup", name="Acme"), final("done")])
    run_agent(decider, make_registry(), "Who?")
    assert "Steps so far: none yet." in decider.turn_prompts[0]
    assert '<observation ok="true">\n{"found":"Acme"}\n</observation>' in decider.turn_prompts[1]


def test_every_turn_gets_the_same_system_prompt_with_the_tools_in_it():
    decider = ScriptedDecider([call("lookup", name="a"), final("done")])
    run_agent(decider, make_registry(), "q")
    assert decider.system_prompts[0] == decider.system_prompts[1]
    assert "lookup(name: string)" in decider.system_prompts[0]


def test_several_tool_calls_are_numbered_in_order():
    decider = ScriptedDecider([call("lookup", name="a"), call("lookup", name="b"), final("ok")])
    result = run_agent(decider, make_registry(), "q")
    assert [(s.number, s.arguments["name"]) for s in result.steps] == [(1, "a"), (2, "b")]


def test_the_final_answer_is_trimmed():
    assert run_agent(ScriptedDecider([final("  padded  ")]), make_registry(), "q").answer == "padded"


def test_tools_receive_validated_arguments_with_defaults():
    calls = []
    decider = ScriptedDecider([call("count"), final("ok")])
    run_agent(decider, make_registry(calls), "q")
    assert calls == [("count", {"limit": 5})]


# ======================= errors become observations the model can react to =======================

def test_an_unknown_tool_is_reported_and_the_agent_can_recover():
    decider = ScriptedDecider([call("delete_all"), call("lookup", name="a"), final("recovered")])
    result = run_agent(decider, make_registry(), "q")
    assert result.steps[0].ok is False
    assert "no tool named 'delete_all'" in result.steps[0].observation
    assert result.steps[1].ok is True
    assert result.answer == "recovered"
    assert "no tool named" in decider.turn_prompts[1]  # the model was told what went wrong


def test_invalid_arguments_are_reported_and_the_tool_does_not_run():
    calls = []
    decider = ScriptedDecider([call("lookup", wrong="x"), final("ok")])
    result = run_agent(decider, make_registry(calls), "q")
    assert result.steps[0].ok is False
    assert "invalid arguments for lookup" in result.steps[0].observation
    assert calls == []


def test_a_tool_error_is_reported_to_the_model():
    result = run_agent(ScriptedDecider([call("broken"), final("sorry")]), make_registry(), "q")
    assert result.steps[0].ok is False
    assert result.steps[0].observation == "Error: Application 9 was not found."


def test_a_decision_that_names_no_tool_is_treated_as_an_error_step():
    decider = ScriptedDecider([Decision(action="tool"), final("ok")])
    result = run_agent(decider, make_registry(), "q")
    assert result.steps[0].ok is False


# ======================= guards =======================

def test_an_identical_repeated_call_is_not_run_twice():
    calls = []
    decider = ScriptedDecider([call("lookup", name="a"), call("lookup", name="a"), final("ok")])
    result = run_agent(decider, make_registry(calls), "q")
    assert len(calls) == 1  # the tool body ran once
    assert result.steps[1].ok is False
    assert "already made this exact call" in result.steps[1].observation


def test_argument_order_does_not_hide_a_repeated_call():
    calls = []
    registry = ToolRegistry([
        Tool("two", "x", (ToolParam("a", "integer", "a"), ToolParam("b", "integer", "b")),
             lambda args: calls.append(args) or {}),
    ])
    decider = ScriptedDecider([call("two", a=1, b=2), call("two", b=2, a=1), final("ok")])
    run_agent(decider, registry, "q")
    assert len(calls) == 1


def test_the_same_tool_with_different_arguments_is_allowed():
    calls = []
    decider = ScriptedDecider([call("lookup", name="a"), call("lookup", name="b"), final("ok")])
    run_agent(decider, make_registry(calls), "q")
    assert len(calls) == 2


def test_the_loop_stops_at_max_steps_with_an_honest_message():
    decider = ScriptedDecider([call("lookup", name=str(n)) for n in range(10)])
    result = run_agent(decider, make_registry(), "q", max_steps=3)
    assert result.stopped_reason == "max_steps"
    assert len(result.steps) == 3
    assert result.answer == GAVE_UP_ANSWER.format(n=3)
    assert len(decider.turn_prompts) == 3  # the model was asked exactly 3 times


def test_only_the_last_turn_tells_the_model_to_wrap_up():
    decider = ScriptedDecider([call("lookup", name="a"), call("lookup", name="b"), final("done")])
    run_agent(decider, make_registry(), "q", max_steps=3)
    assert "LAST step" not in decider.turn_prompts[0]
    assert "LAST step" not in decider.turn_prompts[1]
    assert "LAST step" in decider.turn_prompts[2]


def test_a_model_that_obeys_the_last_step_instruction_still_finishes():
    decider = ScriptedDecider([call("lookup", name="a"), final("Best effort answer.")])
    result = run_agent(decider, make_registry(), "q", max_steps=2)
    assert result.stopped_reason == "final" and result.answer == "Best effort answer."


def test_max_steps_is_kept_within_sensible_bounds():
    decider = ScriptedDecider([call("lookup", name=str(n)) for n in range(30)])
    assert len(run_agent(decider, make_registry(), "q", max_steps=0).steps) == 1
    decider = ScriptedDecider([call("lookup", name=str(n)) for n in range(30)])
    assert len(run_agent(decider, make_registry(), "q", max_steps=500).steps) == HARD_MAX_STEPS


def test_an_empty_final_answer_gets_a_polite_fallback():
    assert run_agent(ScriptedDecider([final("   ")]), make_registry(), "q").answer == NO_ANSWER


def test_errors_from_the_decider_itself_are_not_swallowed():
    with pytest.raises(RuntimeError, match="the model is down"):
        run_agent(ScriptedDecider([RuntimeError("the model is down")]), make_registry(), "q")
