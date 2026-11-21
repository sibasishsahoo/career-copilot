from pathlib import Path

from app.services.rag.notes_file import parse_notes

SAMPLE = Path(__file__).resolve().parents[1] / "samples" / "sample_career_notes.md"


def test_the_sample_file_has_four_notes_with_titles():
    notes = parse_notes(SAMPLE.read_text(encoding="utf-8"))
    assert [title for title, _ in notes] == [
        "Faster deployments for the billing service",
        "Mentoring two interns",
        "Resolving the checkout outage",
        "Cutting API latency with caching",
    ]


def test_the_title_line_is_not_part_of_the_body():
    notes = parse_notes("# My title\nBody line one.\nBody line two.")
    assert notes == [("My title", "Body line one.\nBody line two.")]


def test_notes_without_a_title_get_numbered_names():
    notes = parse_notes("First body.\n---\nSecond body.")
    assert [title for title, _ in notes] == ["Untitled note 1", "Untitled note 2"]


def test_empty_blocks_are_skipped():
    assert parse_notes("# Only a title\n---\n\n---\n# Real\nBody.") == [("Real", "Body.")]


def test_windows_line_endings_work():
    notes = parse_notes("# A\r\nbody a\r\n---\r\n# B\r\nbody b")
    assert [title for title, _ in notes] == ["A", "B"]


def test_empty_file_gives_no_notes():
    assert parse_notes("") == []
    assert parse_notes("\n\n  \n") == []
