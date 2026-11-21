"""The behaviour EVERY vector store must have, written once.

Each function takes `make`, a function that returns a brand-new empty store. The same checks run
against the in-memory store (always) and against Chroma (when it is installed), which proves the two
are interchangeable behind the VectorStore interface.
"""

import pytest

from app.services.rag.models import StoredChunk

NOW = "2026-10-01T10:00:00+00:00"


def make_chunk(doc_id="doc1", index=0, text="some text", title="A title", created_at=NOW, doc_chars=100):
    return StoredChunk(
        id=f"{doc_id}:{index}",
        doc_id=doc_id,
        title=title,
        index=index,
        text=text,
        created_at=created_at,
        doc_chars=doc_chars,
    )


def contract_empty_store(make):
    store = make()
    assert store.count() == 0
    assert store.search([1.0, 0.0, 0.0], k=5) == []
    assert store.list_documents() == []
    assert store.get_document_chunks("nope") == []
    assert store.delete_document("nope") == 0


def contract_add_and_count(make):
    store = make()
    store.add([make_chunk(index=0), make_chunk(index=1)], [[1.0, 0.0, 0.0], [0.0, 1.0, 0.0]])
    assert store.count() == 2


def contract_search_orders_by_similarity(make):
    store = make()
    store.add(
        [make_chunk("far", 0), make_chunk("near", 0), make_chunk("exact", 0)],
        [[0.0, 1.0, 0.0], [0.9, 0.1, 0.0], [1.0, 0.0, 0.0]],
    )
    hits = store.search([1.0, 0.0, 0.0], k=3)
    assert [hit.chunk.doc_id for hit in hits] == ["exact", "near", "far"]
    assert hits[0].score > hits[1].score > hits[2].score


def contract_scores_are_cosine_similarities(make):
    store = make()
    store.add(
        [make_chunk("same", 0), make_chunk("close", 0), make_chunk("perpendicular", 0)],
        [[1.0, 0.0, 0.0], [0.9, 0.1, 0.0], [0.0, 1.0, 0.0]],
    )
    scores = {hit.chunk.doc_id: hit.score for hit in store.search([1.0, 0.0, 0.0], k=3)}
    assert abs(scores["same"] - 1.0) < 1e-3
    assert abs(scores["close"] - 0.99388) < 1e-3  # 0.9 / sqrt(0.9^2 + 0.1^2)
    assert abs(scores["perpendicular"] - 0.0) < 1e-3


def contract_search_limits_results_to_k(make):
    store = make()
    store.add([make_chunk("d", n) for n in range(5)], [[1.0, float(n), 0.0] for n in range(5)])
    assert len(store.search([1.0, 0.0, 0.0], k=2)) == 2
    assert len(store.search([1.0, 0.0, 0.0], k=50)) == 5  # asking for more than exist is fine


def contract_chunks_round_trip_every_field(make):
    original = make_chunk("docX", 3, text="The exact text.", title="My title", created_at=NOW, doc_chars=777)
    store = make()
    store.add([original], [[1.0, 0.0, 0.0]])
    assert store.search([1.0, 0.0, 0.0], k=1)[0].chunk == original
    assert store.get_document_chunks("docX") == [original]


def contract_list_documents_groups_chunks(make):
    store = make()
    store.add(
        [make_chunk("a", n, title="Doc A", doc_chars=500) for n in range(3)]
        + [make_chunk("b", 0, title="Doc B", doc_chars=40, created_at="2026-10-02T09:00:00+00:00")],
        [[1.0, 0.0, 0.0]] * 4,
    )
    infos = {info.doc_id: info for info in store.list_documents()}
    assert set(infos) == {"a", "b"}
    assert (infos["a"].title, infos["a"].chunk_count, infos["a"].char_count) == ("Doc A", 3, 500)
    assert (infos["b"].title, infos["b"].chunk_count, infos["b"].char_count) == ("Doc B", 1, 40)
    assert infos["b"].created_at == "2026-10-02T09:00:00+00:00"


def contract_get_document_chunks_returns_reading_order(make):
    store = make()
    scrambled = [2, 0, 1]
    store.add(
        [make_chunk("d", n, text=f"chunk {n}") for n in scrambled],
        [[1.0, float(n), 0.0] for n in scrambled],
    )
    assert [chunk.index for chunk in store.get_document_chunks("d")] == [0, 1, 2]


def contract_delete_removes_only_that_document(make):
    store = make()
    store.add(
        [make_chunk("keep", 0), make_chunk("drop", 0), make_chunk("drop", 1)],
        [[1.0, 0.0, 0.0], [0.9, 0.1, 0.0], [0.8, 0.2, 0.0]],
    )
    assert store.delete_document("drop") == 2
    assert store.count() == 1
    assert [info.doc_id for info in store.list_documents()] == ["keep"]
    assert [hit.chunk.doc_id for hit in store.search([1.0, 0.0, 0.0], k=5)] == ["keep"]
    assert store.get_document_chunks("drop") == []


def contract_delete_unknown_document_removes_nothing(make):
    store = make()
    store.add([make_chunk("a", 0)], [[1.0, 0.0, 0.0]])
    assert store.delete_document("missing") == 0
    assert store.count() == 1


def contract_mismatched_lengths_are_rejected(make):
    store = make()
    with pytest.raises(ValueError):
        store.add([make_chunk("a", 0), make_chunk("a", 1)], [[1.0, 0.0, 0.0]])
    assert store.count() == 0


ALL_CONTRACTS = [
    contract_empty_store,
    contract_add_and_count,
    contract_search_orders_by_similarity,
    contract_scores_are_cosine_similarities,
    contract_search_limits_results_to_k,
    contract_chunks_round_trip_every_field,
    contract_list_documents_groups_chunks,
    contract_get_document_chunks_returns_reading_order,
    contract_delete_removes_only_that_document,
    contract_delete_unknown_document_removes_nothing,
    contract_mismatched_lengths_are_rejected,
]
