"""Runs the shared vector-store contract against the REAL Chroma database.

Skipped automatically if chromadb is not installed. These tests are how you confirm the Chroma
assumptions in app/services/rag/chroma_store.py on your own machine (in particular that scores are
1 - cosine distance, which contract_scores_are_cosine_similarities checks numerically).
"""

import itertools

import pytest

pytest.importorskip("chromadb")

from app.services.rag.chroma_store import ChromaVectorStore  # noqa: E402
from app.services.rag.factory import build_vector_store  # noqa: E402
from tests import store_contract as contract  # noqa: E402


def factory(tmp_path):
    """Each call returns a brand-new, empty store in its own folder."""
    counter = itertools.count()
    return lambda: ChromaVectorStore(
        path=str(tmp_path / f"db{next(counter)}"), collection_name="career_knowledge_test"
    )


@pytest.mark.parametrize("check", contract.ALL_CONTRACTS, ids=lambda function: function.__name__)
def test_chroma_satisfies_the_vector_store_contract(tmp_path, check):
    check(factory(tmp_path))


def test_data_is_still_there_when_the_database_is_opened_again(tmp_path):
    path = str(tmp_path / "persist")
    first = ChromaVectorStore(path=path, collection_name="career_knowledge_test")
    chunk = contract.make_chunk("keep", 0, text="remember me", doc_chars=42)
    first.add([chunk], [[1.0, 0.0, 0.0]])
    del first

    reopened = ChromaVectorStore(path=path, collection_name="career_knowledge_test")
    assert reopened.count() == 1
    assert reopened.get_document_chunks("keep") == [chunk]
    assert reopened.search([1.0, 0.0, 0.0], k=1)[0].score > 0.99


def test_collections_with_different_names_do_not_see_each_other(tmp_path):
    path = str(tmp_path / "shared")
    local = ChromaVectorStore(path=path, collection_name="career_knowledge_local-minilm")
    hashing = ChromaVectorStore(path=path, collection_name="career_knowledge_hashing-512")
    local.add([contract.make_chunk("a", 0)], [[1.0, 0.0, 0.0]])
    assert local.count() == 1
    assert hashing.count() == 0
    assert hashing.search([1.0, 0.0, 0.0], k=3) == []


def test_the_factory_names_the_collection_after_the_embedder(tmp_path):
    store = build_vector_store("chroma", str(tmp_path / "factory"), "hashing-512")
    assert isinstance(store, ChromaVectorStore)
    assert store._collection.name == "career_knowledge_hashing-512"
