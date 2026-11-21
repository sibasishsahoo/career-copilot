import io

import pytest

from app.services.resume.errors import (
    FileTooLargeError,
    InvalidFileError,
    NoTextFoundError,
    UnsupportedFileTypeError,
)
from app.services.resume.extractor import extract_text, read_limited
from tests.helpers import make_blank_pdf, make_docx, make_pdf


# ---------- happy paths ----------

def test_extracts_docx_paragraphs():
    content = make_docx(["Jane Doe", "Python developer"])
    text = extract_text("resume.docx", content)
    assert "Jane Doe" in text
    assert "Python developer" in text


def test_extracts_docx_table_text():
    content = make_docx(["Skills"], table_rows=[["Python", "SQL"], ["Docker", "Git"]])
    text = extract_text("resume.docx", content)
    assert "Python | SQL" in text
    assert "Docker | Git" in text


def test_extracts_pdf_text():
    text = extract_text("resume.pdf", make_pdf("Jane Doe Python Developer"))
    assert "Jane Doe" in text
    assert "Python Developer" in text


def test_extension_check_is_case_insensitive():
    assert "Hello" in extract_text("RESUME.PDF", make_pdf("Hello World"))


# ---------- rejected files ----------

def test_rejects_unsupported_extension():
    with pytest.raises(UnsupportedFileTypeError, match="PDF or DOCX"):
        extract_text("resume.txt", b"plain text resume")


def test_rejects_missing_extension():
    with pytest.raises(UnsupportedFileTypeError):
        extract_text("resume", b"some bytes")


def test_rejects_empty_file():
    with pytest.raises(InvalidFileError, match="empty"):
        extract_text("resume.pdf", b"")


def test_rejects_fake_pdf():
    # PNG header inside a file named .pdf
    with pytest.raises(InvalidFileError, match="not a PDF"):
        extract_text("resume.pdf", b"\x89PNG\r\n\x1a\n" + b"0" * 100)


def test_rejects_fake_docx():
    with pytest.raises(InvalidFileError, match="not a DOCX"):
        extract_text("resume.docx", b"just some text pretending to be a docx")


def test_rejects_corrupt_pdf():
    with pytest.raises(InvalidFileError, match="could not be read"):
        extract_text("resume.pdf", b"%PDF-1.4 this is garbage, not a real pdf")


def test_rejects_corrupt_docx():
    with pytest.raises(InvalidFileError, match="could not be read"):
        extract_text("resume.docx", b"PK this is not a real zip archive")


def test_pdf_without_text_raises_no_text_found():
    with pytest.raises(NoTextFoundError, match="scanned"):
        extract_text("scan.pdf", make_blank_pdf())


def test_docx_without_text_raises_no_text_found():
    with pytest.raises(NoTextFoundError):
        extract_text("empty.docx", make_docx([""]))


# ---------- size limit ----------

def test_read_limited_accepts_file_under_limit():
    assert read_limited(io.BytesIO(b"12345"), max_bytes=10) == b"12345"


def test_read_limited_accepts_file_exactly_at_limit():
    assert read_limited(io.BytesIO(b"1234567890"), max_bytes=10) == b"1234567890"


def test_read_limited_rejects_file_over_limit():
    with pytest.raises(FileTooLargeError, match="larger than"):
        read_limited(io.BytesIO(b"12345678901"), max_bytes=10)
