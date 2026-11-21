import pytest

from app.services.rag.chunker import _overlap_prefix, chunk_text, normalize_text

SENTENCES = [f"This is sentence number {n} of the test document." for n in range(1, 13)]
LONG_TEXT = " ".join(SENTENCES)


# ---------- basics ----------

def test_empty_and_whitespace_give_no_chunks():
    assert chunk_text("") == []
    assert chunk_text("   \n\n \t ") == []


def test_short_text_is_one_chunk():
    assert chunk_text("Hello world.", chunk_size=100, overlap=10) == ["Hello world."]


def test_text_exactly_chunk_size_is_one_chunk():
    text = "x" * 50
    assert chunk_text(text, chunk_size=50, overlap=5) == [text]


def test_two_short_paragraphs_share_a_chunk_and_keep_their_blank_line():
    chunks = chunk_text("First paragraph.\n\nSecond paragraph.", chunk_size=100, overlap=0)
    assert chunks == ["First paragraph.\n\nSecond paragraph."]


def test_paragraphs_are_kept_whole_when_each_fits():
    first, second = "Alpha beta gamma delta.", "Epsilon zeta eta theta."
    chunks = chunk_text(f"{first}\n\n{second}", chunk_size=30, overlap=0)
    assert chunks == [first, second]


# ---------- splitting a long paragraph ----------

def test_long_paragraph_is_cut_between_sentences():
    chunks = chunk_text(LONG_TEXT, chunk_size=100, overlap=0)
    assert len(chunks) > 1
    for chunk in chunks:
        assert chunk.endswith(".")  # never cut in the middle of a sentence


def test_without_overlap_every_word_is_kept_in_order():
    text = "Intro paragraph here.\n\n" + LONG_TEXT + "\n\nClosing words go here, nothing special."
    chunks = chunk_text(text, chunk_size=90, overlap=0)
    assert " ".join(chunks).split() == text.split()


def test_chunks_never_exceed_size_plus_overlap():
    for size, overlap in [(60, 0), (80, 20), (120, 40), (200, 50)]:
        for chunk in chunk_text(LONG_TEXT, chunk_size=size, overlap=overlap):
            assert len(chunk) <= size + overlap + 1


def test_lines_are_used_when_there_are_no_paragraph_breaks():
    lines = [f"line number {n} has a few words" for n in range(1, 9)]
    chunks = chunk_text("\n".join(lines), chunk_size=70, overlap=0)
    assert len(chunks) > 1
    for chunk in chunks:
        for line in chunk.split("\n"):
            assert line in lines  # every line survived whole


def test_a_gigantic_word_is_cut_blindly_as_a_last_resort():
    text = "x" * 2500
    chunks = chunk_text(text, chunk_size=1000, overlap=0)
    assert [len(chunk) for chunk in chunks] == [1000, 1000, 500]
    assert "".join(chunks) == text


# ---------- overlap ----------

def test_overlap_copies_the_end_of_the_previous_chunk_to_the_start_of_the_next():
    plain = chunk_text(LONG_TEXT, chunk_size=100, overlap=0)
    overlapped = chunk_text(LONG_TEXT, chunk_size=100, overlap=45)
    assert len(overlapped) == len(plain)
    assert overlapped[0] == plain[0]
    for index in range(1, len(plain)):
        prefix = _overlap_prefix(plain[index - 1], 45)
        assert prefix != ""
        assert plain[index - 1].endswith(prefix)
        assert overlapped[index] == f"{prefix} {plain[index]}"


def test_overlap_never_starts_in_the_middle_of_a_word():
    text = " ".join(["abcdefghij"] * 60)
    chunks = chunk_text(text, chunk_size=100, overlap=25)
    for chunk in chunks:
        assert all(word == "abcdefghij" for word in chunk.split())


def test_overlap_prefix_cases():
    assert _overlap_prefix("anything", 0) == ""
    assert _overlap_prefix("", 10) == ""
    assert _overlap_prefix("one two three", 5) == "three"  # tail begins exactly at a word
    assert _overlap_prefix("alpha beta gamma", 8) == "gamma"  # "ta gamma": drop the cut-off "ta"
    assert _overlap_prefix("short", 50) == "short"  # overlap larger than the text: take it all
    assert _overlap_prefix("abcdefghijkl", 4) == ""  # a single cut-off word: nothing clean to keep


# ---------- validation and normalization ----------

def test_invalid_parameters_are_rejected():
    with pytest.raises(ValueError, match="chunk_size"):
        chunk_text("text", chunk_size=0)
    with pytest.raises(ValueError, match="overlap"):
        chunk_text("text", chunk_size=10, overlap=-1)
    with pytest.raises(ValueError, match="overlap"):
        chunk_text("text", chunk_size=10, overlap=10)


def test_windows_line_endings_and_extra_spaces_are_normalized():
    assert chunk_text("a   b\r\n\r\nc", chunk_size=100, overlap=0) == ["a b\n\nc"]


def test_normalize_text_details():
    assert normalize_text("  hello \t world  ") == "hello world"
    assert normalize_text("a\n\n\n\n\nb") == "a\n\nb"
    assert normalize_text("x\x00y\u00a0z") == "xy z"


def test_chunking_is_deterministic():
    assert chunk_text(LONG_TEXT, 100, 30) == chunk_text(LONG_TEXT, 100, 30)


def test_unicode_text_is_fine():
    text = "Café résumé naïve. " * 30
    chunks = chunk_text(text, chunk_size=80, overlap=10)
    assert len(chunks) > 1
    assert all("é" in chunk for chunk in chunks)
