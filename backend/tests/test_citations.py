from app.services.rag.citations import NOT_FOUND_ANSWER, check_citations, is_not_found


# ---------- is_not_found ----------

def test_recognizes_the_not_found_answer():
    assert is_not_found(NOT_FOUND_ANSWER)
    assert is_not_found("  " + NOT_FOUND_ANSWER + "  ")
    assert is_not_found(NOT_FOUND_ANSWER.rstrip("."))
    assert is_not_found(NOT_FOUND_ANSWER.replace("'", "\u2019"))  # curly apostrophe
    assert is_not_found(NOT_FOUND_ANSWER.upper())


def test_a_real_answer_is_not_the_not_found_answer():
    assert not is_not_found("I cut deployment time from 40 to 12 minutes [1].")
    assert not is_not_found("")


# ---------- check_citations ----------

def test_declared_sources_are_kept():
    assert check_citations("I led it [1][2].", [1, 2], source_count=3) == ([1, 2], True)


def test_citations_written_in_the_text_count_even_if_not_declared():
    assert check_citations("I did X [2] and Y [3].", [], source_count=3) == ([2, 3], True)


def test_declared_and_written_citations_are_combined_without_duplicates():
    assert check_citations("I did X [1].", [1, 3], source_count=3) == ([1, 3], True)


def test_numbers_that_do_not_exist_are_dropped():
    assert check_citations("Something [7] and [0].", [7, 0, -1, 99], source_count=3) == ([], False)
    assert check_citations("Real [2] and fake [9].", [9, 2], source_count=3) == ([2], True)


def test_an_answer_without_any_citation_is_not_grounded():
    used, grounded = check_citations("I am great at everything.", [], source_count=3)
    assert used == [] and grounded is False


def test_not_found_is_never_grounded_even_if_sources_are_listed():
    assert check_citations(NOT_FOUND_ANSWER, [1, 2], source_count=3) == ([], False)


def test_multi_digit_citations_work():
    assert check_citations("See [10] and [2].", [], source_count=12) == ([2, 10], True)


def test_results_are_sorted():
    used, _ = check_citations("Facts [3][1][2].", [2, 3], source_count=3)
    assert used == [1, 2, 3]


def test_no_sources_means_nothing_can_be_cited():
    assert check_citations("Answer [1].", [1], source_count=0) == ([], False)
