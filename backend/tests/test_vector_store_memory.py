"""Runs the shared vector-store contract against the in-memory store."""

from app.services.rag.vector_store import InMemoryVectorStore
from tests import store_contract as contract


def make():
    return InMemoryVectorStore()


def test_empty_store():
    contract.contract_empty_store(make)


def test_add_and_count():
    contract.contract_add_and_count(make)


def test_search_orders_by_similarity():
    contract.contract_search_orders_by_similarity(make)


def test_scores_are_cosine_similarities():
    contract.contract_scores_are_cosine_similarities(make)


def test_search_limits_results_to_k():
    contract.contract_search_limits_results_to_k(make)


def test_chunks_round_trip_every_field():
    contract.contract_chunks_round_trip_every_field(make)


def test_list_documents_groups_chunks():
    contract.contract_list_documents_groups_chunks(make)


def test_get_document_chunks_returns_reading_order():
    contract.contract_get_document_chunks_returns_reading_order(make)


def test_delete_removes_only_that_document():
    contract.contract_delete_removes_only_that_document(make)


def test_delete_unknown_document_removes_nothing():
    contract.contract_delete_unknown_document_removes_nothing(make)


def test_mismatched_lengths_are_rejected():
    contract.contract_mismatched_lengths_are_rejected(make)


# ---- behaviour specific to the in-memory store ----

def test_k_zero_or_negative_returns_nothing():
    store = make()
    store.add([contract.make_chunk()], [[1.0, 0.0, 0.0]])
    assert store.search([1.0, 0.0, 0.0], k=0) == []
    assert store.search([1.0, 0.0, 0.0], k=-3) == []


def test_ties_are_broken_deterministically_by_document_and_position():
    store = make()
    same = [1.0, 0.0, 0.0]
    store.add(
        [contract.make_chunk("b", 1), contract.make_chunk("a", 0), contract.make_chunk("b", 0)],
        [same, same, same],
    )
    order = [(hit.chunk.doc_id, hit.chunk.index) for hit in store.search(same, k=3)]
    assert order == [("a", 0), ("b", 0), ("b", 1)]


def test_adding_the_same_chunk_id_again_replaces_it():
    store = make()
    store.add([contract.make_chunk("a", 0, text="old")], [[1.0, 0.0, 0.0]])
    store.add([contract.make_chunk("a", 0, text="new")], [[1.0, 0.0, 0.0]])
    assert store.count() == 1
    assert store.get_document_chunks("a")[0].text == "new"


def test_the_store_keeps_its_own_copy_of_the_vector():
    store = make()
    vector = [1.0, 0.0, 0.0]
    store.add([contract.make_chunk()], [vector])
    vector[0] = -5.0  # changing the caller's list must not corrupt the stored one
    assert store.search([1.0, 0.0, 0.0], k=1)[0].score > 0.99
