import hashlib

import pytest

from app.services.rag.embedder import HashingEmbedder
from app.services.rag.similarity import cosine_similarity, norm


def embed(text: str, dimensions: int = 512) -> list[float]:
    return HashingEmbedder(dimensions).embed([text])[0]


def test_one_vector_per_text_with_the_right_length():
    vectors = HashingEmbedder(128).embed(["first text", "second text", "third"])
    assert len(vectors) == 3
    assert all(len(vector) == 128 for vector in vectors)


def test_no_texts_gives_no_vectors():
    assert HashingEmbedder().embed([]) == []


def test_vectors_have_length_one():
    assert abs(norm(embed("Led the billing migration to Kubernetes")) - 1.0) < 1e-9


def test_same_text_always_gives_the_same_vector_even_in_a_new_instance():
    assert embed("deploy the billing service") == embed("deploy the billing service")


def test_word_positions_come_from_md5_so_they_are_stable_across_runs():
    index = int.from_bytes(hashlib.md5(b"billing").digest()[:4], "big") % 512
    vector = embed("billing")
    assert vector[index] == 1.0
    assert sum(1 for value in vector if value != 0.0) == 1


def test_case_and_word_order_do_not_matter():
    assert embed("Billing Service DEPLOY") == embed("deploy billing service")


def test_text_with_only_stopwords_or_nothing_is_the_zero_vector():
    assert embed("the of and to a") == [0.0] * 512
    assert embed("") == [0.0] * 512
    assert embed("!!! ???") == [0.0] * 512


def test_identical_text_has_similarity_one():
    vector = embed("reduced deployment time for the billing service")
    assert abs(cosine_similarity(vector, vector) - 1.0) < 1e-9


def test_shared_words_make_texts_more_similar_than_unrelated_texts():
    query = embed("billing service deployment")
    related = embed("We improved the billing service deployment pipeline")
    unrelated = embed("Mentoring interns with weekly code reviews")
    assert cosine_similarity(query, related) > cosine_similarity(query, unrelated)
    assert cosine_similarity(query, unrelated) < 0.1


def test_it_is_not_semantic_different_words_for_the_same_idea_do_not_match():
    # The honest limitation: a real embedding model would rate these as similar.
    assert cosine_similarity(embed("car"), embed("automobile")) == 0.0
    assert cosine_similarity(embed("deploy"), embed("deployment")) == 0.0


def test_name_and_default_threshold():
    embedder = HashingEmbedder(256)
    assert embedder.name == "hashing-256"
    assert 0 < embedder.default_min_score < 0.25


def test_dimensions_must_be_reasonable():
    with pytest.raises(ValueError):
        HashingEmbedder(4)
