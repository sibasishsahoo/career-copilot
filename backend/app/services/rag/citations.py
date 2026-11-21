"""Checking the LLM's citations - plain Python, so it is easy to test.

The prompt numbers the sources [1], [2], ... and asks the model to cite them. A model can still
cite a source that does not exist, forget to cite anything, or claim it found nothing. This module
turns the model's claims into facts we can trust more.
"""

import re

NOT_FOUND_ANSWER = "I couldn't find this in your knowledge base."

_CITATION = re.compile(r"\[(\d+)\]")


def is_not_found(answer: str) -> bool:
    normalized = answer.strip().replace("\u2019", "'").lower()
    return normalized.rstrip(".") == NOT_FOUND_ANSWER.lower().rstrip(".")


def check_citations(answer: str, declared: list[int], source_count: int) -> tuple[list[int], bool]:
    """Return (source numbers really used, grounded).

    "Really used" = numbers the model listed OR wrote as [n] in its answer, kept only if they exist
    (1..source_count). `grounded` is True only if the model answered (did not say "not found") AND
    cited at least one real source. An answer with no valid citation cannot be checked against the
    sources, so we flag it instead of presenting it as verified.
    """
    if is_not_found(answer):
        return [], False

    valid_declared = {number for number in declared if 1 <= number <= source_count}
    valid_in_text = {
        int(match) for match in _CITATION.findall(answer) if 1 <= int(match) <= source_count
    }
    used = sorted(valid_declared | valid_in_text)
    return used, bool(used)
