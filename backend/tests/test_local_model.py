"""Tests that use the REAL embedding model. They download about 80 MB the first time, so they only
run when you ask for them:

    RUN_LOCAL_MODEL_TESTS=1 python -m pytest tests/test_local_model.py -v -s

(-s shows the printed scores, which is how you tune RAG_MIN_SCORE for the local model.)
"""

import os
from pathlib import Path

import pytest

pytestmark = pytest.mark.skipif(
    os.environ.get("RUN_LOCAL_MODEL_TESTS") != "1",
    reason="downloads an ~80 MB model; set RUN_LOCAL_MODEL_TESTS=1 to run",
)
pytest.importorskip("chromadb")

from app.services.rag import knowledge_service as knowledge  # noqa: E402
from app.services.rag.embedder import LocalEmbedder  # noqa: E402
from app.services.rag.notes_file import parse_notes  # noqa: E402
from app.services.rag.similarity import cosine_similarity  # noqa: E402
from app.services.rag.vector_store import InMemoryVectorStore  # noqa: E402

SAMPLE = Path(__file__).resolve().parents[1] / "samples" / "sample_career_notes.md"


@pytest.fixture(scope="module")
def embedder():
    return LocalEmbedder()


def test_the_model_returns_384_numbers_per_text(embedder):
    vectors = embedder.embed(["hello world", "another text"])
    assert len(vectors) == 2
    assert all(len(vector) == 384 for vector in vectors)


def test_the_model_understands_meaning_not_just_words(embedder):
    car, automobile, banana = embedder.embed(["car", "automobile", "banana smoothie"])
    related = cosine_similarity(car, automobile)
    unrelated = cosine_similarity(car, banana)
    print(f"\nsimilarity car/automobile = {related:.3f}   car/banana smoothie = {unrelated:.3f}")
    assert related > unrelated  # the hashing embedder would score both 0.0


def test_the_model_finds_the_right_sample_note_even_with_different_words(embedder):
    store = InMemoryVectorStore()
    for title, body in parse_notes(SAMPLE.read_text(encoding="utf-8")):
        knowledge.add_document(store, embedder, title, body, 800, 150)

    expectations = {
        "How did I reduce deployment time?": "Faster deployments for the billing service",
        "Tell me about a time I mentored someone": "Mentoring two interns",
        "When did I handle a production incident or outage?": "Resolving the checkout outage",
        "How did I make the search API faster?": "Cutting API latency with caching",
    }
    print()
    for question, expected_title in expectations.items():
        hits = knowledge.search_chunks(store, embedder, question, k=4)
        scores = ", ".join(f"{hit.score:.2f}" for hit in hits)
        print(f"{question!r:60} -> {hits[0].chunk.title!r}  scores: {scores}")
        assert hits[0].chunk.title == expected_title


def test_an_unrelated_question_scores_lower_than_a_related_one(embedder):
    store = InMemoryVectorStore()
    for title, body in parse_notes(SAMPLE.read_text(encoding="utf-8")):
        knowledge.add_document(store, embedder, title, body, 800, 150)

    related = knowledge.search_chunks(store, embedder, "How did I reduce deployment time?", k=1)[0].score
    unrelated = knowledge.search_chunks(store, embedder, "What is my favourite pizza topping?", k=1)[0].score
    print(f"\nbest score, related question: {related:.3f}   unrelated question: {unrelated:.3f}")
    print(f"current default cut-off for the local model: {embedder.default_min_score}")
    assert related > unrelated
