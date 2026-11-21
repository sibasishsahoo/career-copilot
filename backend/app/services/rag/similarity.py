"""The math behind vector search, written out by hand so nothing is hidden.

An embedding is just a list of numbers (a vector). Texts with similar meaning get vectors that
point in similar directions. Cosine similarity measures the angle between two vectors:

    cosine(a, b) = (a . b) / (|a| * |b|)

    1.0  -> same direction (very similar)
    0.0  -> at right angles (unrelated)
   -1.0  -> opposite directions
"""

import math


def dot(a: list[float], b: list[float]) -> float:
    return sum(x * y for x, y in zip(a, b))


def norm(vector: list[float]) -> float:
    """Length of the vector."""
    return math.sqrt(sum(x * x for x in vector))


def normalize(vector: list[float]) -> list[float]:
    """Scale a vector to length 1. A vector of all zeros has no direction and is returned as is."""
    length = norm(vector)
    if length == 0.0:
        return list(vector)
    return [x / length for x in vector]


def cosine_similarity(a: list[float], b: list[float]) -> float:
    if len(a) != len(b):
        raise ValueError(f"Vectors must have the same length (got {len(a)} and {len(b)}).")
    length_a, length_b = norm(a), norm(b)
    if length_a == 0.0 or length_b == 0.0:
        return 0.0  # a zero vector points nowhere, so it is similar to nothing
    return dot(a, b) / (length_a * length_b)
