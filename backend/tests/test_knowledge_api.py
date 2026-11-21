"""The /knowledge endpoints, end to end: HTTP -> chunking -> embedding -> store -> LLM.

The embedder is the HashingEmbedder, the store is in memory, and the LLM is a scripted fake, so
these tests need no model download, no Chroma and no API key."""

import json

import pytest

from app.api.deps import get_embedder, get_llm, get_vector_store
from app.config import Settings, get_settings
from app.main import app
from app.services.llm.base import LLMConfigError, LLMProviderError, LLMRateLimitError
from app.services.rag.citations import NOT_FOUND_ANSWER
from app.services.rag.embedder import Embedder, HashingEmbedder
from app.services.rag.errors import EmbeddingError, VectorStoreError
from app.services.rag.vector_store import InMemoryVectorStore, VectorStore
from tests.fakes import ScriptedLLM

DEPLOY = (
    "Situation: deployments of the billing service took forty minutes.\n\n"
    "Task: reduce deployment time.\n\n"
    "Action: containerized the service and automated rollbacks.\n\n"
    "Result: deployment time fell to twelve minutes."
)
MENTOR = "I mentored two interns, reviewing their code twice a week and teaching testing."
DEPLOY_QUESTION = "How did I reduce deployment time for the billing service?"


@pytest.fixture
def store():
    return InMemoryVectorStore()


@pytest.fixture
def kb(client, store):
    """The shared test client, wired to the hashing embedder and a fresh in-memory store."""
    app.dependency_overrides[get_embedder] = lambda: HashingEmbedder()
    app.dependency_overrides[get_vector_store] = lambda: store
    return client


def use_llm(llm):
    app.dependency_overrides[get_llm] = lambda: llm


def add(client, title="Faster deploys", text=DEPLOY):
    response = client.post("/knowledge/documents", json={"title": title, "text": text})
    assert response.status_code == 201, response.text
    return response.json()


def cited_reply(answer="I cut deployment time from forty to twelve minutes [1].", used=(1,)):
    return json.dumps({"answer": answer, "sources_used": list(used)})


# ======================= documents =======================

def test_adding_a_document_returns_a_summary(kb):
    body = add(kb)
    assert len(body["id"]) == 32
    assert body["title"] == "Faster deploys"
    assert body["chunk_count"] == 1
    assert body["char_count"] == len(DEPLOY)
    assert body["created_at"].endswith("+00:00")


def test_the_chunk_size_setting_controls_how_documents_are_split(kb):
    app.dependency_overrides[get_settings] = lambda: Settings(
        _env_file=None, rag_chunk_size=100, rag_chunk_overlap=20, gemini_api_key="k"
    )
    assert add(kb)["chunk_count"] > 1


def test_adding_rejects_invalid_bodies(kb):
    url = "/knowledge/documents"
    bad_bodies = {
        "missing title": {"text": DEPLOY},
        "missing text": {"title": "T"},
        "empty title": {"title": "", "text": DEPLOY},
        "blank title": {"title": "   ", "text": DEPLOY},
        "blank text": {"title": "T", "text": "   \n  "},
        "text too long": {"title": "T", "text": "x" * 50_001},
        "title too long": {"title": "t" * 201, "text": DEPLOY},
        "unknown field": {"title": "T", "text": DEPLOY, "tags": ["a"]},
    }
    for label, body in bad_bodies.items():
        assert kb.post(url, json=body).status_code == 422, label


def test_the_list_starts_empty(kb):
    response = kb.get("/knowledge/documents")
    assert response.status_code == 200 and response.json() == []


def test_documents_are_listed_newest_first(kb):
    first = add(kb, "First", DEPLOY)
    second = add(kb, "Second", MENTOR)
    ids = [doc["id"] for doc in kb.get("/knowledge/documents").json()]
    assert ids == [second["id"], first["id"]]


def test_a_document_can_be_viewed_with_its_chunks(kb):
    app.dependency_overrides[get_settings] = lambda: Settings(
        _env_file=None, rag_chunk_size=120, rag_chunk_overlap=20, gemini_api_key="k"
    )
    created = add(kb, text=DEPLOY * 2)
    detail = kb.get(f"/knowledge/documents/{created['id']}").json()
    assert detail["title"] == "Faster deploys"
    assert len(detail["chunks"]) == created["chunk_count"]
    assert [chunk["index"] for chunk in detail["chunks"]] == list(range(created["chunk_count"]))
    assert all(chunk["text"] for chunk in detail["chunks"])


def test_viewing_an_unknown_document_returns_404(kb):
    response = kb.get("/knowledge/documents/nope")
    assert response.status_code == 404
    assert response.json()["detail"] == "Document nope was not found."


def test_deleting_removes_the_document_everywhere(kb):
    created = add(kb)
    response = kb.delete(f"/knowledge/documents/{created['id']}")
    assert response.status_code == 204 and response.content == b""
    assert kb.get(f"/knowledge/documents/{created['id']}").status_code == 404
    assert kb.get("/knowledge/documents").json() == []
    assert kb.post("/knowledge/search", json={"query": "deployment"}).json()["results"] == []


def test_deleting_an_unknown_document_returns_404(kb):
    assert kb.delete("/knowledge/documents/nope").status_code == 404


# ======================= search =======================

def test_search_returns_ranked_results_with_scores(kb):
    deploys = add(kb, "Faster deploys", DEPLOY)
    add(kb, "Mentoring", MENTOR)
    response = kb.post("/knowledge/search", json={"query": DEPLOY_QUESTION, "k": 2})
    assert response.status_code == 200
    body = response.json()
    assert body["query"] == DEPLOY_QUESTION
    first, second = body["results"]
    assert (first["rank"], second["rank"]) == (1, 2)
    assert first["doc_id"] == deploys["id"]
    assert first["title"] == "Faster deploys"
    assert first["chunk_index"] == 0
    assert "deployments of the billing service" in first["text"]
    assert first["score"] > second["score"]
    assert 0.5 < first["score"] <= 1.0


def test_search_returns_at_most_k_results(kb):
    add(kb, "A", DEPLOY)
    add(kb, "B", MENTOR)
    assert len(kb.post("/knowledge/search", json={"query": "deployment", "k": 1}).json()["results"]) == 1


def test_search_on_an_empty_knowledge_base_returns_nothing(kb):
    response = kb.post("/knowledge/search", json={"query": "anything"})
    assert response.status_code == 200 and response.json()["results"] == []


def test_search_rejects_invalid_requests(kb):
    url = "/knowledge/search"
    assert kb.post(url, json={"query": ""}).status_code == 422
    assert kb.post(url, json={"query": "   "}).status_code == 422
    assert kb.post(url, json={"query": "x" * 501}).status_code == 422
    assert kb.post(url, json={"query": "ok", "k": 0}).status_code == 422
    assert kb.post(url, json={"query": "ok", "k": 21}).status_code == 422
    assert kb.post(url, json={}).status_code == 422


# ======================= ask (the full RAG flow) =======================

def test_ask_retrieves_then_answers_with_citations(kb):
    add(kb, "Faster deploys", DEPLOY)
    add(kb, "Mentoring", MENTOR)
    llm = ScriptedLLM([cited_reply()])
    use_llm(llm)

    response = kb.post("/knowledge/ask", json={"question": DEPLOY_QUESTION})
    assert response.status_code == 200
    body = response.json()
    assert body["answer"] == "I cut deployment time from forty to twelve minutes [1]."
    assert body["grounded"] is True
    assert body["used_llm"] is True
    assert body["sources_used"] == [1]
    assert [source["title"] for source in body["sources"]] == ["Faster deploys"]  # the mentoring note scored 0

    prompt = llm.prompts[0]  # the retrieved chunk, and only that one, reached the LLM
    assert DEPLOY_QUESTION in prompt
    assert "deployments of the billing service" in prompt
    assert "mentored two interns" not in prompt


def test_ask_without_relevant_notes_skips_the_llm_entirely(kb):
    add(kb, "Faster deploys", DEPLOY)
    llm = ScriptedLLM([])  # any call would raise AssertionError
    use_llm(llm)
    body = kb.post("/knowledge/ask", json={"question": "pizza toppings volcano"}).json()
    assert body["answer"] == NOT_FOUND_ANSWER
    assert body["grounded"] is False and body["used_llm"] is False
    assert body["sources"] == [] and body["sources_used"] == []
    assert llm.prompts == []


def test_ask_on_an_empty_knowledge_base_says_not_found(kb):
    use_llm(ScriptedLLM([]))
    body = kb.post("/knowledge/ask", json={"question": DEPLOY_QUESTION}).json()
    assert body["answer"] == NOT_FOUND_ANSWER and body["used_llm"] is False


def test_a_stricter_min_score_setting_excludes_matches(kb):
    add(kb)
    app.dependency_overrides[get_settings] = lambda: Settings(
        _env_file=None, rag_min_score=0.99, gemini_api_key="k"
    )
    use_llm(ScriptedLLM([]))
    body = kb.post("/knowledge/ask", json={"question": DEPLOY_QUESTION}).json()
    assert body["used_llm"] is False


def test_ask_cleans_up_citations_that_do_not_exist(kb):
    add(kb)
    use_llm(ScriptedLLM([cited_reply("Made-up source [7].", used=(7,))]))
    body = kb.post("/knowledge/ask", json={"question": DEPLOY_QUESTION}).json()
    assert body["sources_used"] == [] and body["grounded"] is False
    assert body["answer"] == "Made-up source [7]."  # shown, but flagged as not verifiable


def test_an_answer_without_citations_is_flagged_not_grounded(kb):
    add(kb)
    use_llm(ScriptedLLM([cited_reply("Trust me, it was great.", used=())]))
    body = kb.post("/knowledge/ask", json={"question": DEPLOY_QUESTION}).json()
    assert body["grounded"] is False and body["used_llm"] is True


def test_the_model_can_say_it_does_not_know(kb):
    add(kb)
    use_llm(ScriptedLLM([cited_reply(NOT_FOUND_ANSWER, used=())]))
    body = kb.post("/knowledge/ask", json={"question": DEPLOY_QUESTION}).json()
    assert body["answer"] == NOT_FOUND_ANSWER and body["grounded"] is False


def test_ask_retries_bad_model_output_transparently(kb):
    add(kb)
    llm = ScriptedLLM(["not json", cited_reply()])
    use_llm(llm)
    assert kb.post("/knowledge/ask", json={"question": DEPLOY_QUESTION}).status_code == 200
    assert len(llm.prompts) == 2


def test_ask_rejects_invalid_requests(kb):
    use_llm(ScriptedLLM([]))
    url = "/knowledge/ask"
    assert kb.post(url, json={"question": ""}).status_code == 422
    assert kb.post(url, json={"question": "x" * 501}).status_code == 422
    assert kb.post(url, json={"question": "ok", "k": 11}).status_code == 422
    assert kb.post(url, json={}).status_code == 422


def test_ask_maps_llm_failures_to_http_errors(kb):
    add(kb)
    body = {"question": DEPLOY_QUESTION}

    use_llm(ScriptedLLM(["garbage", "more garbage"]))
    assert kb.post("/knowledge/ask", json=body).status_code == 502

    use_llm(ScriptedLLM([LLMRateLimitError("slow down")]))
    assert kb.post("/knowledge/ask", json=body).status_code == 429

    use_llm(ScriptedLLM([LLMProviderError("upstream down")]))
    assert kb.post("/knowledge/ask", json=body).status_code == 502


def test_ask_reports_a_missing_llm_key_as_503(kb):
    add(kb)

    def no_key():
        raise LLMConfigError("GEMINI_API_KEY is not set")

    app.dependency_overrides[get_llm] = no_key
    assert kb.post("/knowledge/ask", json={"question": DEPLOY_QUESTION}).status_code == 503


# ======================= infrastructure failures =======================

class BrokenEmbedder(Embedder):
    name = "broken"

    def embed(self, texts):
        raise EmbeddingError("The local embedding model failed.")


class BrokenStore(VectorStore):
    def _fail(self, *args, **kwargs):
        raise VectorStoreError("Could not open the Chroma database.")

    add = search = list_documents = get_document_chunks = delete_document = count = _fail


def test_an_embedding_failure_returns_503_and_saves_nothing(kb, store):
    app.dependency_overrides[get_embedder] = lambda: BrokenEmbedder()
    response = kb.post("/knowledge/documents", json={"title": "T", "text": DEPLOY})
    assert response.status_code == 503
    assert "embedding model failed" in response.json()["detail"]
    assert store.count() == 0


def test_a_vector_store_failure_returns_503(kb):
    app.dependency_overrides[get_vector_store] = lambda: BrokenStore()
    response = kb.get("/knowledge/documents")
    assert response.status_code == 503
    assert "Chroma" in response.json()["detail"]


def test_an_unknown_embedder_setting_returns_503(client):
    app.dependency_overrides[get_settings] = lambda: Settings(
        _env_file=None, rag_embedder="banana", gemini_api_key="k"
    )
    response = client.get("/knowledge/documents")
    assert response.status_code == 503
    assert "Unknown RAG_EMBEDDER" in response.json()["detail"]
