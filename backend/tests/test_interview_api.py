"""POST/GET/DELETE /applications/{id}/interview-prep end to end, with a scripted AI and in-memory notes."""

import pytest

from app.api.deps import get_knowledge_provider, get_llm
from app.config import Settings, get_settings
from app.main import app
from app.services.llm.base import LLMConfigError, LLMProviderError, LLMRateLimitError
from app.services.rag.errors import EmbeddingError
from tests.fakes import ScriptedLLM
from tests.interview_helpers import JOB_TEXT, answers_reply, notes_env, questions_reply


@pytest.fixture
def prep(client):
    """The shared test client with the notes wired to an in-memory store (two notes)."""
    _, _, provider = notes_env()
    app.dependency_overrides[get_knowledge_provider] = lambda: provider
    return client


def use_llm(llm):
    app.dependency_overrides[get_llm] = lambda: llm


def create_application(client, with_match=True) -> int:
    application = client.post("/applications", json={"company": "Acme Cloud", "job_title": "Backend Engineer"}).json()
    if with_match:
        snapshot = {
            "job_description": JOB_TEXT, "score": 60,
            "matched_skills": [{"skill": "Python", "category": "required"}],
            "missing_skills": [{"skill": "Docker", "category": "required"}],
        }
        assert client.put(f"/applications/{application['id']}/match", json=snapshot).status_code == 200
    return application["id"]


def url(application_id) -> str:
    return f"/applications/{application_id}/interview-prep"


# ======================= generate =======================

def test_generating_returns_the_pack(prep):
    application_id = create_application(prep)
    llm = ScriptedLLM([questions_reply(), answers_reply()])
    use_llm(llm)

    response = prep.post(url(application_id), params={"question_count": 3})
    assert response.status_code == 200
    body = response.json()
    assert (body["application_id"], body["company"], body["job_title"]) == (application_id, "Acme Cloud", "Backend Engineer")
    assert body["generated_at"].endswith("+00:00")
    assert [item["story_found"] for item in body["items"]] == [True, True, False]
    assert body["items"][0]["sources"] == ["Faster deployments"]
    assert "[Faster deployments]" in body["items"][0]["answer_outline"]
    assert body["items"][2]["note"].startswith("No note in your knowledge base matched")
    assert body["coverage"] == {"total": 3, "with_story": 2, "without_story": [3]}
    assert body["questions_to_ask"] == ["What does success look like in six months?"]
    assert len(llm.prompts) == 2


def test_the_saved_pack_can_be_read_back_without_an_llm_call(prep):
    application_id = create_application(prep)
    use_llm(ScriptedLLM([questions_reply(), answers_reply()]))
    created = prep.post(url(application_id), params={"question_count": 3}).json()

    use_llm(ScriptedLLM([]))  # reading must not call the AI
    fetched = prep.get(url(application_id))
    assert fetched.status_code == 200 and fetched.json() == created


def test_regenerating_replaces_the_pack(prep):
    application_id = create_application(prep)
    use_llm(ScriptedLLM([questions_reply(), answers_reply(), questions_reply(), answers_reply()]))
    prep.post(url(application_id), params={"question_count": 3})
    second = prep.post(url(application_id), params={"question_count": 3}).json()
    assert prep.get(url(application_id)).json() == second


def test_the_question_count_comes_from_the_query_or_the_settings(prep):
    application_id = create_application(prep)
    llm = ScriptedLLM([questions_reply(), answers_reply(), questions_reply(), answers_reply()])
    use_llm(llm)
    prep.post(url(application_id), params={"question_count": 5})
    app.dependency_overrides[get_settings] = lambda: Settings(_env_file=None, interview_question_count=6, gemini_api_key="k")
    prep.post(url(application_id))
    assert "exactly 5 questions" in llm.system_prompts[0]
    assert "exactly 6 questions" in llm.system_prompts[2]


def test_the_question_count_is_validated(prep):
    application_id = create_application(prep)
    use_llm(ScriptedLLM([]))
    for bad in (2, 13, 0, -1):
        assert prep.post(url(application_id), params={"question_count": bad}).status_code == 422, bad


def test_without_any_notes_the_pack_still_lists_questions_and_costs_one_call(client):
    _, _, provider = notes_env(with_notes=False)
    app.dependency_overrides[get_knowledge_provider] = lambda: provider
    application_id = create_application(client)
    llm = ScriptedLLM([questions_reply()])
    use_llm(llm)
    body = client.post(url(application_id), params={"question_count": 3}).json()
    assert body["coverage"] == {"total": 3, "with_story": 0, "without_story": [1, 2, 3]}
    assert len(llm.prompts) == 1


# ======================= not ready / not found =======================

def test_an_application_without_a_saved_match_gets_a_409_that_says_what_to_do(prep):
    application_id = create_application(prep, with_match=False)
    use_llm(ScriptedLLM([]))
    response = prep.post(url(application_id))
    assert response.status_code == 409
    assert "saved job match" in response.json()["detail"] and "Match tool" in response.json()["detail"]


def test_an_unknown_application_returns_404_everywhere(prep):
    use_llm(ScriptedLLM([]))
    assert prep.post(url(999)).status_code == 404
    assert prep.get(url(999)).status_code == 404
    assert prep.delete(url(999)).status_code == 404


def test_reading_a_pack_that_was_never_generated_returns_404_with_a_hint(prep):
    application_id = create_application(prep)
    response = prep.get(url(application_id))
    assert response.status_code == 404
    assert f"POST /applications/{application_id}/interview-prep" in response.json()["detail"]


# ======================= delete =======================

def test_deleting_the_pack(prep):
    application_id = create_application(prep)
    use_llm(ScriptedLLM([questions_reply(), answers_reply()]))
    prep.post(url(application_id), params={"question_count": 3})

    assert prep.delete(url(application_id)).status_code == 204
    assert prep.get(url(application_id)).status_code == 404
    assert prep.delete(url(application_id)).status_code == 404


def test_deleting_the_application_removes_its_pack(prep):
    application_id = create_application(prep)
    use_llm(ScriptedLLM([questions_reply(), answers_reply()]))
    prep.post(url(application_id), params={"question_count": 3})
    assert prep.delete(f"/applications/{application_id}").status_code == 204
    assert prep.get(url(application_id)).status_code == 404


# ======================= failures =======================

def test_an_unavailable_knowledge_base_returns_503_without_spending_an_llm_call(client):
    def broken():
        raise EmbeddingError("The local embedding model failed.")

    app.dependency_overrides[get_knowledge_provider] = lambda: broken
    application_id = create_application(client)
    llm = ScriptedLLM([])
    use_llm(llm)
    response = client.post(url(application_id))
    assert response.status_code == 503 and "embedding model failed" in response.json()["detail"]
    assert llm.prompts == []


def test_ai_output_that_stays_invalid_returns_502_and_saves_nothing(prep):
    application_id = create_application(prep)
    use_llm(ScriptedLLM(["garbage", "more garbage"]))
    response = prep.post(url(application_id))
    assert response.status_code == 502 and "valid structured data" in response.json()["detail"]
    assert prep.get(url(application_id)).status_code == 404


def test_bad_output_is_retried_transparently(prep):
    application_id = create_application(prep)
    llm = ScriptedLLM(["not json", questions_reply(), answers_reply()])
    use_llm(llm)
    assert prep.post(url(application_id), params={"question_count": 3}).status_code == 200
    assert len(llm.prompts) == 3


def test_llm_provider_failures_map_to_http_errors(prep):
    application_id = create_application(prep)

    use_llm(ScriptedLLM([LLMRateLimitError("slow down")]))
    assert prep.post(url(application_id)).status_code == 429

    use_llm(ScriptedLLM([LLMProviderError("upstream down")]))
    assert prep.post(url(application_id)).status_code == 502

    def no_key():
        raise LLMConfigError("GEMINI_API_KEY is not set")

    app.dependency_overrides[get_llm] = no_key
    assert prep.post(url(application_id)).status_code == 503
