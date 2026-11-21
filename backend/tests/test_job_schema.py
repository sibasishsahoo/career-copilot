import copy

import pytest
from pydantic import ValidationError

from app.schemas.job import (
    MAX_JOB_CHARS,
    MIN_JOB_CHARS,
    JobAnalysis,
    JobAnalyzeRequest,
    JobMatchRequest,
    SkillComparison,
    SkillMatch,
    SuggestionList,
)
from app.services.job.prompts import EXAMPLE_JOB
from app.services.resume.prompts import EXAMPLE_RESUME


def valid_job() -> dict:
    return copy.deepcopy(EXAMPLE_JOB)


def locations(exc_info) -> list[tuple]:
    return [error["loc"] for error in exc_info.value.errors()]


# ---------- JobAnalysis: valid ----------

def test_full_valid_job():
    job = JobAnalysis.model_validate(valid_job())
    assert job.job_title == "Backend Engineer"
    assert job.required_skills == ["Python", "SQL", "REST APIs"]
    assert job.min_years_experience == 3


def test_minimal_job_uses_defaults():
    job = JobAnalysis.model_validate(
        {"job_title": "Dev", "required_skills": [], "preferred_skills": [], "responsibilities": []}
    )
    assert job.company is None
    assert job.min_years_experience is None


def test_prompt_example_is_a_valid_job():
    # Guards against the prompt's example drifting out of sync with the schema.
    JobAnalysis.model_validate(EXAMPLE_JOB)


# ---------- JobAnalysis: missing fields ----------

def test_missing_job_title():
    data = valid_job()
    del data["job_title"]
    with pytest.raises(ValidationError) as exc_info:
        JobAnalysis.model_validate(data)
    assert ("job_title",) in locations(exc_info)


def test_empty_job_title_is_rejected():
    data = valid_job()
    data["job_title"] = ""
    with pytest.raises(ValidationError):
        JobAnalysis.model_validate(data)


def test_missing_required_skills():
    data = valid_job()
    del data["required_skills"]
    with pytest.raises(ValidationError) as exc_info:
        JobAnalysis.model_validate(data)
    assert ("required_skills",) in locations(exc_info)


def test_missing_preferred_skills():
    data = valid_job()
    del data["preferred_skills"]
    with pytest.raises(ValidationError) as exc_info:
        JobAnalysis.model_validate(data)
    assert ("preferred_skills",) in locations(exc_info)


# ---------- JobAnalysis: wrong types ----------

def test_skills_as_one_string_is_rejected():
    data = valid_job()
    data["required_skills"] = "Python, SQL"
    with pytest.raises(ValidationError) as exc_info:
        JobAnalysis.model_validate(data)
    assert ("required_skills",) in locations(exc_info)


def test_skills_null_is_rejected():
    data = valid_job()
    data["preferred_skills"] = None
    with pytest.raises(ValidationError):
        JobAnalysis.model_validate(data)


def test_years_as_words_is_rejected():
    data = valid_job()
    data["min_years_experience"] = "three plus"
    with pytest.raises(ValidationError) as exc_info:
        JobAnalysis.model_validate(data)
    assert ("min_years_experience",) in locations(exc_info)


def test_years_numeric_string_is_converted():
    data = valid_job()
    data["min_years_experience"] = "3"
    assert JobAnalysis.model_validate(data).min_years_experience == 3


def test_number_where_text_expected_is_rejected():
    data = valid_job()
    data["company"] = 42
    with pytest.raises(ValidationError):
        JobAnalysis.model_validate(data)


# ---------- request bodies ----------

def test_job_text_of_minimum_length_is_accepted():
    JobAnalyzeRequest(job_description="x" * MIN_JOB_CHARS)


def test_job_text_too_short_is_rejected():
    with pytest.raises(ValidationError):
        JobAnalyzeRequest(job_description="x" * (MIN_JOB_CHARS - 1))


def test_job_text_too_long_is_rejected():
    with pytest.raises(ValidationError):
        JobAnalyzeRequest(job_description="x" * (MAX_JOB_CHARS + 1))


def test_surrounding_whitespace_does_not_count_towards_length():
    with pytest.raises(ValidationError):
        JobAnalyzeRequest(job_description="   " + "x" * (MIN_JOB_CHARS - 1) + "   ")


def test_match_request_requires_a_resume():
    with pytest.raises(ValidationError) as exc_info:
        JobMatchRequest(job_description="x" * 60)
    assert ("resume",) in locations(exc_info)


def test_match_request_validates_the_nested_resume():
    bad_resume = {k: v for k, v in EXAMPLE_RESUME.items() if k != "full_name"}
    with pytest.raises(ValidationError) as exc_info:
        JobMatchRequest(resume=bad_resume, job_description="x" * 60)
    assert ("resume", "full_name") in locations(exc_info)


def test_match_request_accepts_a_valid_resume():
    request = JobMatchRequest(resume=EXAMPLE_RESUME, job_description="x" * 60)
    assert request.resume.full_name == "Jane Doe"


# ---------- other schemas ----------

def test_suggestion_list_must_not_be_empty():
    with pytest.raises(ValidationError):
        SuggestionList(suggestions=[])


def test_suggestions_must_be_a_list_of_strings():
    with pytest.raises(ValidationError):
        SuggestionList(suggestions="Learn Docker")


def test_score_must_be_between_0_and_100():
    empty = {"matched": [], "missing": []}
    with pytest.raises(ValidationError):
        SkillComparison(score=101, required=empty, preferred=empty)
    with pytest.raises(ValidationError):
        SkillComparison(score=-1, required=empty, preferred=empty)


def test_found_in_only_allows_known_values():
    SkillMatch(skill="Python", found_in="skills_section")
    with pytest.raises(ValidationError):
        SkillMatch(skill="Python", found_in="somewhere_else")
