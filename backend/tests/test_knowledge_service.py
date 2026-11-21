"""The knowledge-base logic end to end (chunk -> embed -> store -> search) with a fake-free setup:
the real chunker and the HashingEmbedder, an in-memory store, and no network."""

import time
from pathlib import Path

import pytest

from app.services.rag import knowledge_service as ks
from app.services.rag.embedder import Embedder, HashingEmbedder
from app.services.rag.errors import DocumentNotFoundError, EmbeddingError, EmptyDocumentError
from app.services.rag.notes_file import parse_notes
from app.services.rag.vector_store import InMemoryVectorStore

SAMPLE = Path(__file__).resolve().parents[1] / "samples" / "sample_career_notes.md"

DEPLOY_NOTE = (
    "Situation: deployments of the billing service took forty minutes.\n\n"
    "Task: reduce deployment time.\n\n"
    "Action: containerized the service and automated rollbacks.\n\n"
    "Result: deployment time fell to twelve minutes."
)
MENTOR_NOTE = "I mentored two interns, reviewing their code twice a week and teaching testing."


class RecordingEmbedder(Embedder):
    """Wraps another embedder and remembers every text it was asked to embed."""

    name = "recording"

    def __init__(self):
        self.inner = HashingEmbedder()
        self.seen: list[str] = []

    def embed(self, texts):
        self.seen.extend(texts)
        return self.inner.embed(texts)


class BrokenEmbedder(Embedder):
    name = "broken"

    def embed(self, texts):
        raise EmbeddingError("model unavailable")


class ShortChangeEmbedder(Embedder):
    name = "short"

    def embed(self, texts):
        return [[1.0, 0.0]]  # always one vector, whatever was asked


def fresh():
    return InMemoryVectorStore(), HashingEmbedder()


# ---------- add_document ----------

def test_add_document_returns_information_about_what_was_stored():
    store, embedder = fresh()
    info = ks.add_document(store, embedder, "  Faster deploys  ", DEPLOY_NOTE, 800, 150)
    assert info.title == "Faster deploys"
    assert info.chunk_count == 1
    assert info.char_count == len(DEPLOY_NOTE)
    assert len(info.doc_id) == 32
    assert info.created_at.endswith("+00:00")
    assert store.count() == info.chunk_count


def test_a_long_document_becomes_several_ordered_chunks():
    store, embedder = fresh()
    info = ks.add_document(store, embedder, "Long", DEPLOY_NOTE * 4, 120, 30)
    assert info.chunk_count > 3
    chunks = store.get_document_chunks(info.doc_id)
    assert [chunk.index for chunk in chunks] == list(range(info.chunk_count))
    assert len({chunk.created_at for chunk in chunks}) == 1
    assert all(chunk.title == "Long" for chunk in chunks)
    assert all(chunk.doc_chars == info.char_count for chunk in chunks)


def test_the_title_is_embedded_together_with_each_chunk():
    store, _ = fresh()
    embedder = RecordingEmbedder()
    ks.add_document(store, embedder, "Faster deploys", DEPLOY_NOTE, 800, 0)
    assert embedder.seen == ["Faster deploys\n" + DEPLOY_NOTE]
    # ...but the stored chunk text is the plain chunk, without the title
    assert store.search(embedder.inner.embed(["deploy"])[0], 1)[0].chunk.text == DEPLOY_NOTE


def test_a_blank_title_becomes_untitled():
    store, embedder = fresh()
    assert ks.add_document(store, embedder, "   ", MENTOR_NOTE, 800, 0).title == "Untitled"


def test_a_document_without_text_is_rejected_and_nothing_is_stored():
    store, embedder = fresh()
    with pytest.raises(EmptyDocumentError):
        ks.add_document(store, embedder, "Empty", "  \n\n  ", 800, 150)
    assert store.count() == 0


def test_if_embedding_fails_nothing_is_stored():
    store = InMemoryVectorStore()
    with pytest.raises(EmbeddingError, match="model unavailable"):
        ks.add_document(store, BrokenEmbedder(), "T", DEPLOY_NOTE, 800, 150)
    assert store.count() == 0


def test_a_wrong_number_of_vectors_is_an_error():
    store = InMemoryVectorStore()
    with pytest.raises(EmbeddingError, match="wrong number"):
        ks.add_document(store, ShortChangeEmbedder(), "T", DEPLOY_NOTE * 4, 120, 30)
    assert store.count() == 0


# ---------- list / get / delete ----------

def test_documents_are_listed_newest_first():
    store, embedder = fresh()
    first = ks.add_document(store, embedder, "First", DEPLOY_NOTE, 800, 0)
    time.sleep(0.01)
    second = ks.add_document(store, embedder, "Second", MENTOR_NOTE, 800, 0)
    assert [info.doc_id for info in ks.list_documents(store)] == [second.doc_id, first.doc_id]


def test_get_document_returns_info_and_chunks():
    store, embedder = fresh()
    added = ks.add_document(store, embedder, "Doc", DEPLOY_NOTE * 3, 150, 20)
    info, chunks = ks.get_document(store, added.doc_id)
    assert info == added
    assert len(chunks) == added.chunk_count


def test_get_unknown_document_raises():
    store, _ = fresh()
    with pytest.raises(DocumentNotFoundError, match="abc"):
        ks.get_document(store, "abc")


def test_delete_removes_the_document_and_reports_the_chunk_count():
    store, embedder = fresh()
    keep = ks.add_document(store, embedder, "Keep", MENTOR_NOTE, 800, 0)
    drop = ks.add_document(store, embedder, "Drop", DEPLOY_NOTE * 3, 150, 20)
    assert ks.delete_document(store, drop.doc_id) == drop.chunk_count
    assert [info.doc_id for info in ks.list_documents(store)] == [keep.doc_id]
    with pytest.raises(DocumentNotFoundError):
        ks.delete_document(store, drop.doc_id)  # already gone


# ---------- search ----------

def test_search_ranks_the_relevant_document_first():
    store, embedder = fresh()
    ks.add_document(store, embedder, "Faster deploys", DEPLOY_NOTE, 800, 0)
    ks.add_document(store, embedder, "Mentoring", MENTOR_NOTE, 800, 0)
    hits = ks.search_chunks(store, embedder, "reduce deployment time for the billing service", k=2)
    assert [hit.chunk.title for hit in hits] == ["Faster deploys", "Mentoring"]
    assert hits[0].score > hits[1].score


def test_search_returns_at_most_k_hits():
    store, embedder = fresh()
    ks.add_document(store, embedder, "Doc", DEPLOY_NOTE * 5, 100, 0)
    assert len(ks.search_chunks(store, embedder, "deployment", k=2)) == 2


def test_min_score_drops_weak_matches():
    store, embedder = fresh()
    ks.add_document(store, embedder, "Faster deploys", DEPLOY_NOTE, 800, 0)
    ks.add_document(store, embedder, "Mentoring", MENTOR_NOTE, 800, 0)
    everything = ks.search_chunks(store, embedder, "deployment time billing service", k=5)
    strict = ks.search_chunks(store, embedder, "deployment time billing service", k=5, min_score=0.2)
    assert len(everything) == 2
    assert [hit.chunk.title for hit in strict] == ["Faster deploys"]


def test_an_unrelated_question_finds_nothing_above_the_threshold():
    store, embedder = fresh()
    ks.add_document(store, embedder, "Faster deploys", DEPLOY_NOTE, 800, 0)
    hits = ks.search_chunks(store, embedder, "pizza toppings volcano", k=3, min_score=embedder.default_min_score)
    assert hits == []


def test_searching_an_empty_store_returns_nothing():
    store, embedder = fresh()
    assert ks.search_chunks(store, embedder, "anything at all", k=3) == []


def test_an_empty_query_is_rejected():
    store, embedder = fresh()
    with pytest.raises(ValueError):
        ks.search_chunks(store, embedder, "   ", k=3)


def test_the_query_is_embedded_by_the_same_embedder_exactly_once():
    store = InMemoryVectorStore()
    embedder = RecordingEmbedder()
    ks.add_document(store, embedder, "Doc", DEPLOY_NOTE, 800, 0)
    embedder.seen.clear()
    ks.search_chunks(store, embedder, "  billing deployment  ", k=1)
    assert embedder.seen == ["billing deployment"]


# ---------- with the real sample notes ----------

def load_sample():
    store, embedder = fresh()
    for title, body in parse_notes(SAMPLE.read_text(encoding="utf-8")):
        ks.add_document(store, embedder, title, body, 800, 150)
    return store, embedder


def test_sample_notes_latency_question_finds_the_caching_note():
    store, embedder = load_sample()
    hits = ks.search_chunks(store, embedder, "How did I improve database performance and latency?", k=3)
    assert hits[0].chunk.title == "Cutting API latency with caching"


def test_sample_notes_outage_question_finds_the_incident_note():
    store, embedder = load_sample()
    hits = ks.search_chunks(store, embedder, "When did I handle a production incident or outage?", k=3)
    assert hits[0].chunk.title == "Resolving the checkout outage"


def test_sample_notes_are_chunked_when_the_chunk_size_is_small():
    store, embedder = fresh()
    title, body = parse_notes(SAMPLE.read_text(encoding="utf-8"))[0]
    info = ks.add_document(store, embedder, title, body, 200, 40)
    assert info.chunk_count >= 3
