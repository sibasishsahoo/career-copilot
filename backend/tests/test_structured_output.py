"""Tests for the generic ask -> extract -> validate -> retry loop.

We use a tiny Person model here (not ParsedResume) on purpose: this machinery is
independent of resumes. ScriptedLLM plays the model and hands back prepared replies.
"""

import pytest
from pydantic import BaseModel

from app.services.llm.base import LLMOutputError, LLMProviderError
from app.services.llm.structured import generate_structured
from tests.fakes import ScriptedLLM


class Person(BaseModel):
    name: str
    age: int
    tags: list[str]


VALID = '{"name": "Ana", "age": 30, "tags": ["a", "b"]}'


def ask(llm, **kwargs):
    return generate_structured(llm, "Describe a person.", Person, system_prompt="SYS", **kwargs)


# ---------- valid responses ----------

def test_valid_reply_on_first_try_needs_one_call():
    llm = ScriptedLLM([VALID])
    person = ask(llm)
    assert person == Person(name="Ana", age=30, tags=["a", "b"])
    assert len(llm.prompts) == 1
    assert llm.prompts[0] == "Describe a person."


def test_reply_wrapped_in_code_fence_is_accepted():
    llm = ScriptedLLM([f"```json\n{VALID}\n```"])
    assert ask(llm).name == "Ana"
    assert len(llm.prompts) == 1


def test_pydantic_lax_mode_converts_numeric_strings():
    # "30" is a string, but Pydantic can safely convert it to the int 30.
    llm = ScriptedLLM(['{"name": "Ana", "age": "30", "tags": []}'])
    assert ask(llm).age == 30
    assert len(llm.prompts) == 1


def test_system_prompt_is_forwarded_on_every_attempt():
    llm = ScriptedLLM(["not json", VALID])
    ask(llm)
    assert llm.system_prompts == ["SYS", "SYS"]


# ---------- malformed JSON ----------

def test_malformed_json_triggers_one_retry_then_succeeds():
    llm = ScriptedLLM(['{"name": "Ana", "age": 30,', VALID])
    assert ask(llm).name == "Ana"
    assert len(llm.prompts) == 2


def test_retry_prompt_contains_original_request_error_and_previous_reply():
    bad = '{"name": "Ana", "age": 30,'
    llm = ScriptedLLM([bad, VALID])
    ask(llm)
    retry_prompt = llm.prompts[1]
    assert "Describe a person." in retry_prompt  # original request
    assert "malformed JSON" in retry_prompt  # what went wrong
    assert bad in retry_prompt  # the model's own bad reply


def test_reply_with_no_json_triggers_retry():
    llm = ScriptedLLM(["Sorry, I cannot do that.", VALID])
    assert ask(llm).age == 30
    assert "No JSON object" in llm.prompts[1]


# ---------- missing fields ----------

def test_missing_field_triggers_retry_naming_the_field():
    llm = ScriptedLLM(['{"name": "Ana", "tags": []}', VALID])
    assert ask(llm).age == 30
    assert "age: Field required" in llm.prompts[1]


def test_multiple_missing_fields_are_all_reported():
    llm = ScriptedLLM(['{"name": "Ana"}', VALID])
    ask(llm)
    assert "age" in llm.prompts[1]
    assert "tags" in llm.prompts[1]


# ---------- incorrect data types ----------

def test_wrong_type_for_number_triggers_retry():
    llm = ScriptedLLM(['{"name": "Ana", "age": "thirty", "tags": []}', VALID])
    assert ask(llm).age == 30
    assert "age" in llm.prompts[1]
    assert "valid integer" in llm.prompts[1]


def test_string_where_list_expected_triggers_retry():
    llm = ScriptedLLM(['{"name": "Ana", "age": 30, "tags": "a, b"}', VALID])
    assert ask(llm).tags == ["a", "b"]
    assert "tags" in llm.prompts[1]
    assert "valid list" in llm.prompts[1]


def test_null_where_value_required_triggers_retry():
    llm = ScriptedLLM(['{"name": null, "age": 30, "tags": []}', VALID])
    assert ask(llm).name == "Ana"
    assert "name" in llm.prompts[1]


# ---------- giving up ----------

def test_gives_up_after_default_retry_and_raises_output_error():
    llm = ScriptedLLM(["garbage one", "garbage two"])
    with pytest.raises(LLMOutputError, match="after 2 attempts"):
        ask(llm)
    assert len(llm.prompts) == 2  # 1 first try + 1 retry, no more


def test_final_error_message_includes_last_problem():
    llm = ScriptedLLM(["garbage", '{"name": "Ana", "tags": []}'])
    with pytest.raises(LLMOutputError, match="age: Field required"):
        ask(llm)


def test_zero_retries_means_exactly_one_call():
    llm = ScriptedLLM(["garbage"])
    with pytest.raises(LLMOutputError, match="after 1 attempts"):
        ask(llm, max_retries=0)
    assert len(llm.prompts) == 1


def test_more_retries_allow_later_success():
    llm = ScriptedLLM(["bad", "worse", VALID])
    assert ask(llm, max_retries=2).name == "Ana"
    assert len(llm.prompts) == 3


# ---------- provider errors are not retried ----------

def test_provider_error_passes_through_without_retry():
    llm = ScriptedLLM([LLMProviderError("boom"), VALID])
    with pytest.raises(LLMProviderError, match="boom") as excinfo:
        ask(llm)
    assert type(excinfo.value) is LLMProviderError  # not the LLMOutputError subclass
    assert len(llm.prompts) == 1
