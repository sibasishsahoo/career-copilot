import math

import pytest

from app.services.rag.similarity import cosine_similarity, dot, norm, normalize


def close(a: float, b: float, tolerance: float = 1e-9) -> bool:
    return abs(a - b) < tolerance


def test_dot_product():
    assert dot([1, 2, 3], [4, 5, 6]) == 32


def test_norm_is_the_length_of_the_vector():
    assert norm([3, 4]) == 5
    assert norm([0, 0, 0]) == 0


def test_normalize_gives_length_one():
    assert close(norm(normalize([3.0, 4.0])), 1.0)
    assert normalize([3.0, 4.0]) == [0.6, 0.8]


def test_normalize_leaves_a_zero_vector_alone():
    assert normalize([0.0, 0.0]) == [0.0, 0.0]


def test_identical_vectors_have_similarity_one():
    assert close(cosine_similarity([1.0, 2.0, 3.0], [1.0, 2.0, 3.0]), 1.0)


def test_perpendicular_vectors_have_similarity_zero():
    assert close(cosine_similarity([1.0, 0.0], [0.0, 1.0]), 0.0)


def test_opposite_vectors_have_similarity_minus_one():
    assert close(cosine_similarity([1.0, 2.0], [-1.0, -2.0]), -1.0)


def test_similarity_ignores_length_and_only_looks_at_direction():
    assert close(cosine_similarity([1.0, 2.0], [10.0, 20.0]), 1.0)


def test_known_value():
    expected = 32 / (math.sqrt(14) * math.sqrt(77))
    assert close(cosine_similarity([1, 2, 3], [4, 5, 6]), expected)
    assert close(expected, 0.9746318461970762, 1e-12)


def test_zero_vector_is_similar_to_nothing():
    assert cosine_similarity([0.0, 0.0], [1.0, 1.0]) == 0.0
    assert cosine_similarity([1.0, 1.0], [0.0, 0.0]) == 0.0


def test_vectors_of_different_length_are_rejected():
    with pytest.raises(ValueError, match="same length"):
        cosine_similarity([1.0, 2.0], [1.0, 2.0, 3.0])
