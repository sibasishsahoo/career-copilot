import json

import pytest

from app.services.llm.base import LLMOutputError, LLMProviderError
from app.services.rag.answerer import answer_question
from app.services.rag.citations import NOT_FOUND_ANSWER
from app.services.rag.models import SearchHit
from app.services.rag.prompts import ANSWER_SYSTEM_PROMPT
from tests.fakes import ScriptedLLM
from tests.store_contract import make_chunk


def hit(title: str, text: str, score: float = 0.8) -> SearchHit:
    return SearchHit(make_chunk(doc_id=title, title=title, text=text), score)


HITS = [
    hit("Faster deploys", "Deployment time fell from 40 to 12 minutes."),
    hit("Mentoring", "I mentored two interns and reviewed their code."),
]
QUESTION = "How did I cut deployment time?"


def reply(answer: str, used: list[int]) -> str:
    return json.dumps({"answer": answer, "sources_used": used})


# ---------- valid answers ----------

def test_a_cited_answer_is_grounded():
    llm = ScriptedLLM([reply("I cut deployment time from 40 to 12 minutes [1].", [1])])
    answer = answer_question(llm, QUESTION, HITS)
    assert answer.text == "I cut deployment time from 40 to 12 minutes [1]."
    assert answer.sources_used == [1]
    assert answer.grounded is True
    assert len(llm.prompts) == 1


def test_the_prompt_contains_the_question_and_the_numbered_sources():
    llm = ScriptedLLM([reply("Answer [1].", [1])])
    answer_question(llm, QUESTION, HITS)
    prompt = llm.prompts[0]
    assert f"Question: {QUESTION}" in prompt
    assert '<source id="1" title="Faster deploys">' in prompt
    assert "Deployment time fell from 40 to 12 minutes." in prompt
    assert '<source id="2" title="Mentoring">' in prompt


def test_the_grounding_system_prompt_is_used():
    llm = ScriptedLLM([reply("Answer [1].", [1])])
    answer_question(llm, QUESTION, HITS)
    assert llm.system_prompts[0] == ANSWER_SYSTEM_PROMPT


def test_the_answer_text_is_trimmed():
    llm = ScriptedLLM([reply("  Padded answer [2].  ", [2])])
    assert answer_question(llm, QUESTION, HITS).text == "Padded answer [2]."


def test_reply_in_a_code_fence_is_accepted():
    llm = ScriptedLLM(["```json\n" + reply("Fenced [1].", [1]) + "\n```"])
    assert answer_question(llm, QUESTION, HITS).grounded is True


# ---------- the citation checks ----------

def test_not_found_is_not_grounded():
    llm = ScriptedLLM([reply(NOT_FOUND_ANSWER, [])])
    answer = answer_question(llm, QUESTION, HITS)
    assert answer.text == NOT_FOUND_ANSWER
    assert answer.sources_used == [] and answer.grounded is False


def test_citations_of_sources_that_do_not_exist_are_removed():
    llm = ScriptedLLM([reply("Something [5].", [5])])
    answer = answer_question(llm, QUESTION, HITS)
    assert answer.sources_used == [] and answer.grounded is False


def test_an_answer_with_no_citation_is_flagged_as_not_grounded():
    llm = ScriptedLLM([reply("I am simply wonderful.", [])])
    answer = answer_question(llm, QUESTION, HITS)
    assert answer.text == "I am simply wonderful."
    assert answer.grounded is False


def test_a_citation_written_only_in_the_text_still_counts():
    llm = ScriptedLLM([reply("From the second note [2].", [])])
    answer = answer_question(llm, QUESTION, HITS)
    assert answer.sources_used == [2] and answer.grounded is True


# ---------- retries: malformed JSON, missing fields, wrong types ----------

def test_malformed_json_is_retried():
    llm = ScriptedLLM(['{"answer": "Half an answ', reply("Good [1].", [1])])
    assert answer_question(llm, QUESTION, HITS).text == "Good [1]."
    assert len(llm.prompts) == 2
    assert "malformed JSON" in llm.prompts[1]


def test_a_missing_sources_used_field_is_retried_and_named():
    llm = ScriptedLLM([json.dumps({"answer": "No list [1]."}), reply("With list [1].", [1])])
    answer_question(llm, QUESTION, HITS)
    assert "sources_used: Field required" in llm.prompts[1]


def test_a_missing_answer_field_is_retried_and_named():
    llm = ScriptedLLM([json.dumps({"sources_used": [1]}), reply("Now there is one [1].", [1])])
    answer_question(llm, QUESTION, HITS)
    assert "answer: Field required" in llm.prompts[1]


def test_an_empty_answer_is_rejected_and_retried():
    llm = ScriptedLLM([reply("", [1]), reply("Real answer [1].", [1])])
    assert answer_question(llm, QUESTION, HITS).text == "Real answer [1]."
    assert "answer" in llm.prompts[1]


def test_sources_used_as_a_string_is_a_type_error_and_retried():
    llm = ScriptedLLM([json.dumps({"answer": "x [1]", "sources_used": "1"}), reply("Fixed [1].", [1])])
    answer_question(llm, QUESTION, HITS)
    assert "sources_used" in llm.prompts[1]
    assert "valid list" in llm.prompts[1]


def test_sources_used_with_non_numbers_is_a_type_error_and_retried():
    llm = ScriptedLLM([json.dumps({"answer": "x", "sources_used": ["first"]}), reply("Fixed [1].", [1])])
    answer_question(llm, QUESTION, HITS)
    assert "sources_used.0" in llm.prompts[1]


def test_gives_up_after_two_bad_replies():
    llm = ScriptedLLM(["not json", "still not json"])
    with pytest.raises(LLMOutputError):
        answer_question(llm, QUESTION, HITS)
    assert len(llm.prompts) == 2


def test_provider_errors_pass_through_without_a_retry():
    llm = ScriptedLLM([LLMProviderError("boom")])
    with pytest.raises(LLMProviderError, match="boom"):
        answer_question(llm, QUESTION, HITS)
    assert len(llm.prompts) == 1
