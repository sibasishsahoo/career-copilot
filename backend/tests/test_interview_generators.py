"""The two LLM steps: prompts out, validated structures back, retries on bad output."""

import json

import pytest

from app.services.interview.generators import LLMAnswerDrafter, LLMQuestionGenerator
from app.services.interview.models import DraftedAnswer, DraftingInput, JobContext, Question, QuestionSources, Source
from app.services.interview.prompts import DRAFTING_SYSTEM_PROMPT
from app.services.llm.base import LLMOutputError, LLMProviderError
from tests.fakes import ScriptedLLM

JOB = JobContext(7, "Acme Cloud", "Backend Engineer", "We need Python and Docker.", 60, ["Python"], ["Docker"])

QUESTION = {"text": "Tell me about a time you led a project.", "category": "behavioral",
            "why_asked": "Leadership.", "skill": None}
QUESTIONS_REPLY = json.dumps({"questions": [QUESTION, {**QUESTION, "text": "How would you use Docker?", "category": "gap", "skill": "Docker"}],
                              "questions_to_ask": ["What does success look like?"]})


def questions(replies):
    llm = ScriptedLLM(replies)
    return LLMQuestionGenerator(llm)(JOB, 8), llm


# ======================= step 1: questions =======================

def test_questions_are_parsed_into_a_plan():
    plan, llm = questions([QUESTIONS_REPLY])
    assert [(q.text, q.category, q.skill) for q in plan.questions] == [
        ("Tell me about a time you led a project.", "behavioral", None),
        ("How would you use Docker?", "gap", "Docker"),
    ]
    assert all(q.number == 0 for q in plan.questions)  # the pipeline numbers them, not the model
    assert plan.questions_to_ask == ["What does success look like?"]
    assert len(llm.prompts) == 1


def test_the_prompts_contain_the_job_and_the_requested_count():
    _, llm = questions([QUESTIONS_REPLY])
    assert "exactly 8 questions" in llm.system_prompts[0]
    assert "Backend Engineer at Acme Cloud" in llm.prompts[0]
    assert "We need Python and Docker." in llm.prompts[0]


def test_a_reply_in_a_code_fence_is_accepted():
    plan, _ = questions(["```json\n" + QUESTIONS_REPLY + "\n```"])
    assert len(plan.questions) == 2


def test_optional_fields_may_be_left_out():
    minimal = json.dumps({"questions": [{"text": "A question long enough?", "category": "role"}]})
    plan, _ = questions([minimal])
    assert plan.questions[0].why_asked == "" and plan.questions[0].skill is None
    assert plan.questions_to_ask == []


def test_malformed_json_is_retried():
    plan, llm = questions(['{"questions": [', QUESTIONS_REPLY])
    assert len(plan.questions) == 2 and "malformed JSON" in llm.prompts[1]


def test_a_missing_questions_field_is_retried_and_named():
    _, llm = questions([json.dumps({"questions_to_ask": []}), QUESTIONS_REPLY])
    assert "questions: Field required" in llm.prompts[1]


def test_an_empty_question_list_is_rejected_and_retried():
    _, llm = questions([json.dumps({"questions": []}), QUESTIONS_REPLY])
    assert "questions" in llm.prompts[1] and "at least 1 item" in llm.prompts[1]


def test_an_unknown_category_is_retried_and_pinpointed():
    bad = json.dumps({"questions": [{**QUESTION, "category": "trick"}]})
    _, llm = questions([bad, QUESTIONS_REPLY])
    assert "questions.0.category" in llm.prompts[1]


def test_a_question_that_is_too_short_is_retried():
    bad = json.dumps({"questions": [{**QUESTION, "text": "Why?"}]})
    _, llm = questions([bad, QUESTIONS_REPLY])
    assert "questions.0.text" in llm.prompts[1]


def test_questions_as_a_string_is_a_type_error_and_retried():
    _, llm = questions([json.dumps({"questions": "Tell me about yourself"}), QUESTIONS_REPLY])
    assert "valid list" in llm.prompts[1]


def test_the_question_step_gives_up_after_two_bad_replies():
    llm = ScriptedLLM(["nope", "still nope"])
    with pytest.raises(LLMOutputError):
        LLMQuestionGenerator(llm)(JOB, 8)
    assert len(llm.prompts) == 2


def test_provider_errors_pass_through_the_question_step():
    llm = ScriptedLLM([LLMProviderError("boom")])
    with pytest.raises(LLMProviderError, match="boom"):
        LLMQuestionGenerator(llm)(JOB, 8)


# ======================= step 2: answers =======================

Q1 = Question(1, "Tell me about improving deployments.", "behavioral", "why", None)
DRAFTING = DraftingInput(JOB, [QuestionSources(Q1, [1])], [Source(1, "Faster deployments", "I cut deploys to 12 minutes.")])
ANSWERS_REPLY = json.dumps({"answers": [{"question_id": 1, "fits": True, "outline": "I cut deploys [1].", "sources_used": [1]}]})


def answers(replies):
    llm = ScriptedLLM(replies)
    return LLMAnswerDrafter(llm)(DRAFTING), llm


def test_answers_are_parsed():
    result, llm = answers([ANSWERS_REPLY])
    assert result == [DraftedAnswer(1, True, "I cut deploys [1].", [1])]
    assert len(llm.prompts) == 1


def test_the_drafting_prompts_are_the_grounded_ones():
    _, llm = answers([ANSWERS_REPLY])
    assert llm.system_prompts[0] == DRAFTING_SYSTEM_PROMPT
    assert '<source id="1" title="Faster deployments">' in llm.prompts[0]
    assert 'sources="1"' in llm.prompts[0]


def test_a_story_that_does_not_fit_may_have_an_empty_outline():
    reply = json.dumps({"answers": [{"question_id": 1, "fits": False, "outline": "", "sources_used": []}]})
    result, _ = answers([reply])
    assert result == [DraftedAnswer(1, False, "", [])]


def test_fits_without_an_outline_is_rejected_and_retried():
    bad = json.dumps({"answers": [{"question_id": 1, "fits": True, "outline": "  ", "sources_used": [1]}]})
    _, llm = answers([bad, ANSWERS_REPLY])
    assert '"outline" is required when "fits" is true' in llm.prompts[1]


def test_a_missing_question_id_is_retried_and_named():
    bad = json.dumps({"answers": [{"fits": False}]})
    _, llm = answers([bad, ANSWERS_REPLY])
    assert "answers.0.question_id: Field required" in llm.prompts[1]


def test_sources_used_as_text_is_a_type_error_and_retried():
    bad = json.dumps({"answers": [{"question_id": 1, "fits": True, "outline": "x [1]", "sources_used": "1"}]})
    _, llm = answers([bad, ANSWERS_REPLY])
    assert "answers.0.sources_used" in llm.prompts[1] and "valid list" in llm.prompts[1]


def test_a_missing_answers_field_is_retried():
    _, llm = answers([json.dumps({"result": []}), ANSWERS_REPLY])
    assert "answers: Field required" in llm.prompts[1]


def test_the_answer_step_gives_up_after_two_bad_replies():
    llm = ScriptedLLM(["nope", "still nope"])
    with pytest.raises(LLMOutputError):
        LLMAnswerDrafter(llm)(DRAFTING)
    assert len(llm.prompts) == 2


def test_provider_errors_pass_through_the_answer_step():
    llm = ScriptedLLM([LLMProviderError("boom")])
    with pytest.raises(LLMProviderError, match="boom"):
        LLMAnswerDrafter(llm)(DRAFTING)
    assert len(llm.prompts) == 1
