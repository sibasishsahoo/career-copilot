import json

import pytest

from app.schemas.job import JobAnalysis
from app.schemas.resume import ParsedResume
from app.services.job.matcher import compare_resume_to_job
from app.services.job.prompts import SUGGESTIONS_SYSTEM_PROMPT
from app.services.job.suggestions import generate_suggestions
from app.services.llm.base import LLMOutputError
from tests.fakes import ScriptedLLM

GOOD_REPLY = json.dumps({"suggestions": ["Learn Docker by containerizing a project.", "Add metrics."]})

RESUME = ParsedResume(
    full_name="Jane Doe",
    skills=["Python", "SQL"],
    experience=[{"company": "Acme", "title": "Engineer", "highlights": ["Built a billing API"]}],
    education=[],
)


def setup(required, preferred):
    job = JobAnalysis(
        job_title="Backend Engineer",
        required_skills=required,
        preferred_skills=preferred,
        responsibilities=[],
    )
    return job, compare_resume_to_job(RESUME, job)


# ---------- the LLM is skipped when there is nothing to say ----------

def test_no_llm_call_when_nothing_is_missing():
    job, comparison = setup(required=["Python"], preferred=["SQL"])
    llm = ScriptedLLM([])  # any call would raise AssertionError
    assert generate_suggestions(llm, RESUME, job, comparison) == []
    assert llm.prompts == []


# ---------- the LLM is given the computed facts ----------

def test_returns_the_models_suggestions():
    job, comparison = setup(required=["Python", "Kubernetes"], preferred=["Docker"])
    llm = ScriptedLLM([GOOD_REPLY])
    suggestions = generate_suggestions(llm, RESUME, job, comparison)
    assert suggestions == ["Learn Docker by containerizing a project.", "Add metrics."]
    assert len(llm.prompts) == 1


def test_prompt_contains_gaps_matches_title_and_resume_digest():
    job, comparison = setup(required=["Python", "Kubernetes"], preferred=["Docker"])
    llm = ScriptedLLM([GOOD_REPLY])
    generate_suggestions(llm, RESUME, job, comparison)
    prompt = llm.prompts[0]
    assert "Backend Engineer" in prompt
    assert "already shows: Python" in prompt
    assert "missing from the resume: Kubernetes" in prompt
    assert "Preferred skills missing from the resume: Docker" in prompt
    assert "Built a billing API" in prompt  # from the resume digest


def test_uses_the_suggestions_system_prompt():
    job, comparison = setup(required=["Kubernetes"], preferred=[])
    llm = ScriptedLLM([GOOD_REPLY])
    generate_suggestions(llm, RESUME, job, comparison)
    assert llm.system_prompts[0] == SUGGESTIONS_SYSTEM_PROMPT


# ---------- retries ----------

def test_malformed_json_is_retried():
    job, comparison = setup(required=["Kubernetes"], preferred=[])
    llm = ScriptedLLM(['{"suggestions": ["a", ', GOOD_REPLY])
    assert len(generate_suggestions(llm, RESUME, job, comparison)) == 2
    assert len(llm.prompts) == 2


def test_empty_suggestion_list_is_rejected_and_retried():
    job, comparison = setup(required=["Kubernetes"], preferred=[])
    llm = ScriptedLLM([json.dumps({"suggestions": []}), GOOD_REPLY])
    generate_suggestions(llm, RESUME, job, comparison)
    assert "suggestions" in llm.prompts[1]


def test_wrong_type_is_retried():
    job, comparison = setup(required=["Kubernetes"], preferred=[])
    llm = ScriptedLLM([json.dumps({"suggestions": "Learn Docker"}), GOOD_REPLY])
    generate_suggestions(llm, RESUME, job, comparison)
    assert "valid list" in llm.prompts[1]


def test_missing_field_is_retried():
    job, comparison = setup(required=["Kubernetes"], preferred=[])
    llm = ScriptedLLM([json.dumps({"tips": ["x"]}), GOOD_REPLY])
    generate_suggestions(llm, RESUME, job, comparison)
    assert "suggestions: Field required" in llm.prompts[1]


def test_gives_up_after_two_bad_replies():
    job, comparison = setup(required=["Kubernetes"], preferred=[])
    llm = ScriptedLLM(["nope", "nope again"])
    with pytest.raises(LLMOutputError):
        generate_suggestions(llm, RESUME, job, comparison)
    assert len(llm.prompts) == 2
