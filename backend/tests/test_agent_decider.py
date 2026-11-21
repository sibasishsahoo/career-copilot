"""The adapter that asks the LLM for the agent's next decision (JSON -> validated -> Decision)."""

import json

import pytest

from app.services.agent.decider import LLMDecider
from app.services.agent.models import Decision
from app.services.llm.base import LLMOutputError, LLMProviderError
from tests.fakes import ScriptedLLM

SYSTEM = "SYSTEM PROMPT"
TURN = "TURN PROMPT"


def decide(replies):
    llm = ScriptedLLM(replies)
    return LLMDecider(llm)(SYSTEM, TURN), llm


TOOL_REPLY = json.dumps(
    {"thought": "Need the list.", "action": "tool", "tool": "list_applications", "arguments": {"status": "applied"}}
)
FINAL_REPLY = json.dumps({"thought": "Done.", "action": "final", "answer": "You have two applications."})


# ---------- valid decisions ----------

def test_a_tool_decision_is_parsed():
    decision, llm = decide([TOOL_REPLY])
    assert decision == Decision(
        action="tool", thought="Need the list.", tool="list_applications", arguments={"status": "applied"}, answer=None
    )
    assert len(llm.prompts) == 1


def test_a_final_decision_is_parsed():
    decision, _ = decide([FINAL_REPLY])
    assert decision.action == "final" and decision.answer == "You have two applications."
    assert decision.arguments == {}


def test_null_or_missing_arguments_become_an_empty_dict():
    null_args = json.dumps({"action": "final", "answer": "ok", "arguments": None})
    no_args = json.dumps({"action": "final", "answer": "ok"})
    assert decide([null_args])[0].arguments == {}
    assert decide([no_args])[0].arguments == {}


def test_the_thought_is_optional():
    decision, _ = decide([json.dumps({"action": "tool", "tool": "list_applications"})])
    assert decision.thought is None and decision.arguments == {}


def test_a_reply_in_a_code_fence_is_accepted():
    assert decide(["```json\n" + FINAL_REPLY + "\n```"])[0].action == "final"


def test_the_prompts_are_passed_to_the_llm_unchanged():
    _, llm = decide([FINAL_REPLY])
    assert llm.system_prompts[0] == SYSTEM
    assert llm.prompts[0] == TURN


# ---------- retries: malformed JSON, missing fields, wrong types ----------

def test_malformed_json_is_retried():
    decision, llm = decide(['{"action": "tool", "tool": ', FINAL_REPLY])
    assert decision.action == "final"
    assert len(llm.prompts) == 2
    assert "malformed JSON" in llm.prompts[1]


def test_a_missing_action_is_retried_and_named():
    _, llm = decide([json.dumps({"tool": "x"}), FINAL_REPLY])
    assert "action: Field required" in llm.prompts[1]


def test_an_unknown_action_is_retried():
    _, llm = decide([json.dumps({"action": "think", "answer": "hmm"}), FINAL_REPLY])
    assert "action" in llm.prompts[1]


def test_a_tool_action_without_a_tool_name_is_retried_with_a_clear_message():
    _, llm = decide([json.dumps({"action": "tool"}), TOOL_REPLY])
    assert '"tool" is required when action is "tool"' in llm.prompts[1]


def test_a_final_action_without_an_answer_is_retried_with_a_clear_message():
    _, llm = decide([json.dumps({"action": "final", "thought": "done"}), FINAL_REPLY])
    assert '"answer" is required when action is "final"' in llm.prompts[1]


def test_arguments_that_are_not_an_object_are_retried():
    wrong = json.dumps({"action": "tool", "tool": "x", "arguments": "status=applied"})
    _, llm = decide([wrong, TOOL_REPLY])
    assert "arguments" in llm.prompts[1] and "valid dictionary" in llm.prompts[1]


def test_gives_up_after_two_bad_replies():
    llm = ScriptedLLM(["not json", "still not json"])
    with pytest.raises(LLMOutputError):
        LLMDecider(llm)(SYSTEM, TURN)
    assert len(llm.prompts) == 2


def test_provider_errors_pass_through_without_a_retry():
    llm = ScriptedLLM([LLMProviderError("boom")])
    with pytest.raises(LLMProviderError, match="boom"):
        LLMDecider(llm)(SYSTEM, TURN)
    assert len(llm.prompts) == 1
