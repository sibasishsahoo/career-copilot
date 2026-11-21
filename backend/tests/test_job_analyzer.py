import json

import pytest

from app.services.job.analyzer import analyze_job
from app.services.job.errors import EmptyJobDescriptionError
from app.services.job.prompts import ANALYSIS_SYSTEM_PROMPT, EXAMPLE_JOB
from app.services.llm.base import LLMOutputError
from tests.fakes import ScriptedLLM

VALID_REPLY = json.dumps(EXAMPLE_JOB)
JOB_TEXT = "We are hiring a Backend Engineer. Requirements: Python, SQL, REST APIs."


def test_parses_valid_reply():
    llm = ScriptedLLM([VALID_REPLY])
    job = analyze_job(llm, JOB_TEXT)
    assert job.job_title == "Backend Engineer"
    assert job.required_skills == ["Python", "SQL", "REST APIs"]
    assert job.preferred_skills == ["Docker", "AWS"]
    assert len(llm.prompts) == 1


def test_reply_in_code_fence_is_accepted():
    llm = ScriptedLLM([f"```json\n{VALID_REPLY}\n```"])
    assert analyze_job(llm, JOB_TEXT).company == "Acme Corp"


def test_prompt_wraps_job_text_in_markers():
    llm = ScriptedLLM([VALID_REPLY])
    analyze_job(llm, "MY SPECIAL JOB TEXT")
    assert "<job_description>\nMY SPECIAL JOB TEXT\n</job_description>" in llm.prompts[0]


def test_uses_the_analysis_system_prompt():
    llm = ScriptedLLM([VALID_REPLY])
    analyze_job(llm, JOB_TEXT)
    assert llm.system_prompts[0] == ANALYSIS_SYSTEM_PROMPT


def test_job_text_is_cleaned_before_sending():
    llm = ScriptedLLM([VALID_REPLY])
    analyze_job(llm, "Python    developer\r\n\r\n\r\n\r\nwanted")
    assert "Python developer\n\nwanted" in llm.prompts[0]


def test_empty_job_text_is_rejected_without_calling_the_llm():
    llm = ScriptedLLM([])
    with pytest.raises(EmptyJobDescriptionError):
        analyze_job(llm, "  \n\t ")
    assert llm.prompts == []


# ---------- retries: malformed JSON, missing fields, wrong types ----------

def test_malformed_json_is_retried():
    llm = ScriptedLLM(['{"job_title": "Dev", ', VALID_REPLY])
    assert analyze_job(llm, JOB_TEXT).job_title == "Backend Engineer"
    assert len(llm.prompts) == 2
    assert "malformed JSON" in llm.prompts[1]


def test_missing_field_is_retried_and_named():
    incomplete = {k: v for k, v in EXAMPLE_JOB.items() if k != "required_skills"}
    llm = ScriptedLLM([json.dumps(incomplete), VALID_REPLY])
    analyze_job(llm, JOB_TEXT)
    assert "required_skills: Field required" in llm.prompts[1]


def test_wrong_type_for_skills_is_retried_and_named():
    wrong = dict(EXAMPLE_JOB, required_skills="Python, SQL")
    llm = ScriptedLLM([json.dumps(wrong), VALID_REPLY])
    analyze_job(llm, JOB_TEXT)
    assert "required_skills" in llm.prompts[1]
    assert "valid list" in llm.prompts[1]


def test_wrong_type_for_years_is_retried_and_named():
    wrong = dict(EXAMPLE_JOB, min_years_experience="3+")
    llm = ScriptedLLM([json.dumps(wrong), VALID_REPLY])
    analyze_job(llm, JOB_TEXT)
    assert "min_years_experience" in llm.prompts[1]


def test_gives_up_after_two_bad_replies():
    llm = ScriptedLLM(["nope", "still nope"])
    with pytest.raises(LLMOutputError, match="after 2 attempts"):
        analyze_job(llm, JOB_TEXT)
    assert len(llm.prompts) == 2
