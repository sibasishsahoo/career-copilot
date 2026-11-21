import copy
import json

from app.api.deps import get_llm
from app.main import app
from app.services.job.prompts import EXAMPLE_JOB
from app.services.llm.base import LLMProviderError, LLMRateLimitError
from app.services.resume.prompts import EXAMPLE_RESUME
from tests.fakes import ScriptedLLM

JOB_TEXT = "We are hiring a Backend Engineer. Requirements: Python, SQL, REST APIs. Nice to have: Docker, AWS."
ANALYSIS_REPLY = json.dumps(EXAMPLE_JOB)  # required: Python, SQL, REST APIs / preferred: Docker, AWS
SUGGESTIONS_REPLY = json.dumps({"suggestions": ["Learn Docker.", "Quantify your API work."]})


def use_llm(llm):
    app.dependency_overrides[get_llm] = lambda: llm


def match_body(resume=None, job_description=JOB_TEXT) -> dict:
    return {"resume": resume or copy.deepcopy(EXAMPLE_RESUME), "job_description": job_description}


# ======================= POST /jobs/analyze =======================

def test_analyze_returns_structured_job(client):
    llm = ScriptedLLM([ANALYSIS_REPLY])
    use_llm(llm)
    response = client.post("/jobs/analyze", json={"job_description": JOB_TEXT})
    assert response.status_code == 200
    body = response.json()
    assert body["job_title"] == "Backend Engineer"
    assert body["required_skills"] == ["Python", "SQL", "REST APIs"]
    assert len(llm.prompts) == 1
    assert JOB_TEXT in llm.prompts[0]


def test_analyze_retries_transparently(client):
    llm = ScriptedLLM(["not json", ANALYSIS_REPLY])
    use_llm(llm)
    assert client.post("/jobs/analyze", json={"job_description": JOB_TEXT}).status_code == 200
    assert len(llm.prompts) == 2


def test_analyze_rejects_too_short_text_without_calling_the_llm(client):
    llm = ScriptedLLM([])
    use_llm(llm)
    assert client.post("/jobs/analyze", json={"job_description": "too short"}).status_code == 422
    assert llm.prompts == []


def test_analyze_rejects_too_long_text(client):
    use_llm(ScriptedLLM([]))
    response = client.post("/jobs/analyze", json={"job_description": "x" * 15_001})
    assert response.status_code == 422


def test_analyze_requires_the_field(client):
    use_llm(ScriptedLLM([]))
    assert client.post("/jobs/analyze", json={}).status_code == 422


def test_analyze_invalid_model_output_returns_502(client):
    use_llm(ScriptedLLM(["garbage", "more garbage"]))
    response = client.post("/jobs/analyze", json={"job_description": JOB_TEXT})
    assert response.status_code == 502
    assert "valid structured data" in response.json()["detail"]


def test_analyze_rate_limit_returns_429(client):
    use_llm(ScriptedLLM([LLMRateLimitError("slow down")]))
    assert client.post("/jobs/analyze", json={"job_description": JOB_TEXT}).status_code == 429


def test_analyze_provider_failure_returns_502(client):
    use_llm(ScriptedLLM([LLMProviderError("upstream down")]))
    assert client.post("/jobs/analyze", json={"job_description": JOB_TEXT}).status_code == 502


# ======================= POST /jobs/match =======================

def test_match_full_flow(client):
    llm = ScriptedLLM([ANALYSIS_REPLY, SUGGESTIONS_REPLY])
    use_llm(llm)
    response = client.post("/jobs/match", json=match_body())
    assert response.status_code == 200
    body = response.json()

    assert body["job"]["job_title"] == "Backend Engineer"
    assert body["required"]["matched"] == [
        {"skill": "Python", "found_in": "skills_section"},
        {"skill": "SQL", "found_in": "skills_section"},
    ]
    assert body["required"]["missing"] == ["REST APIs"]
    assert body["preferred"]["matched"] == []
    assert body["preferred"]["missing"] == ["Docker", "AWS"]
    assert body["score"] == 47  # computed by code: 0.7 * 2/3 + 0.3 * 0
    assert body["suggestions"] == ["Learn Docker.", "Quantify your API work."]

    assert len(llm.prompts) == 2  # one analysis call + one suggestions call
    assert "REST APIs" in llm.prompts[1]  # the computed gap reached the suggestions prompt


def test_match_perfect_resume_skips_the_suggestions_call(client):
    resume = copy.deepcopy(EXAMPLE_RESUME)
    resume["skills"] = ["Python", "SQL", "REST APIs", "Docker", "AWS"]
    llm = ScriptedLLM([ANALYSIS_REPLY])  # a second call would raise AssertionError
    use_llm(llm)
    response = client.post("/jobs/match", json=match_body(resume))
    assert response.status_code == 200
    body = response.json()
    assert body["score"] == 100
    assert body["suggestions"] == []
    assert len(llm.prompts) == 1


def test_match_retry_in_analysis_step(client):
    llm = ScriptedLLM(["not json", ANALYSIS_REPLY, SUGGESTIONS_REPLY])
    use_llm(llm)
    assert client.post("/jobs/match", json=match_body()).status_code == 200
    assert len(llm.prompts) == 3


def test_match_job_without_skills_returns_422(client):
    no_skills = dict(copy.deepcopy(EXAMPLE_JOB), required_skills=[], preferred_skills=[])
    llm = ScriptedLLM([json.dumps(no_skills)])
    use_llm(llm)
    response = client.post("/jobs/match", json=match_body())
    assert response.status_code == 422
    assert "does not list any skills" in response.json()["detail"]
    assert len(llm.prompts) == 1


def test_match_invalid_resume_returns_422_without_calling_the_llm(client):
    llm = ScriptedLLM([])
    use_llm(llm)
    bad_resume = {k: v for k, v in EXAMPLE_RESUME.items() if k != "full_name"}
    assert client.post("/jobs/match", json=match_body(bad_resume)).status_code == 422
    assert llm.prompts == []


def test_match_requires_job_description(client):
    use_llm(ScriptedLLM([]))
    body = {"resume": copy.deepcopy(EXAMPLE_RESUME)}
    assert client.post("/jobs/match", json=body).status_code == 422


def test_match_rejects_short_job_description(client):
    use_llm(ScriptedLLM([]))
    assert client.post("/jobs/match", json=match_body(job_description="short")).status_code == 422


def test_match_bad_suggestions_output_returns_502(client):
    use_llm(ScriptedLLM([ANALYSIS_REPLY, "garbage", "more garbage"]))
    response = client.post("/jobs/match", json=match_body())
    assert response.status_code == 502


def test_match_rate_limit_during_suggestions_returns_429(client):
    use_llm(ScriptedLLM([ANALYSIS_REPLY, LLMRateLimitError("slow down")]))
    assert client.post("/jobs/match", json=match_body()).status_code == 429
