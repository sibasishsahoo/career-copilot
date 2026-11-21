"""Steps 1-2 of the pipeline: validate the upload and extract its raw text.

We never trust the filename alone. A file called "resume.pdf" could be anything,
so we also check the first bytes of the content (the "magic bytes"):
    PDF  files start with  %PDF
    DOCX files are ZIP archives and start with  PK
"""

import io
from pathlib import Path

from app.services.resume.errors import (
    FileTooLargeError,
    InvalidFileError,
    NoTextFoundError,
    UnsupportedFileTypeError,
)

ALLOWED_EXTENSIONS = {".pdf", ".docx"}
MAX_UPLOAD_BYTES = 5 * 1024 * 1024  # 5 MB
MAX_PDF_PAGES = 20  # a resume longer than this is unusual; protects against huge files


def read_limited(file_obj, max_bytes: int) -> bytes:
    """Read an upload, refusing files bigger than max_bytes.

    We read max_bytes + 1: if we actually get that extra byte, the file is too big.
    This avoids loading a giant file fully into memory just to reject it.
    (A reverse proxy such as nginx should also enforce a limit in production.)
    """
    data = file_obj.read(max_bytes + 1)
    if len(data) > max_bytes:
        raise FileTooLargeError(f"The file is larger than the allowed limit of {max_bytes:,} bytes.")
    return data


def extract_text(filename: str, content: bytes) -> str:
    """Return the raw text of a PDF or DOCX resume."""
    if not content:
        raise InvalidFileError("The uploaded file is empty.")

    extension = Path(filename).suffix.lower()
    if extension not in ALLOWED_EXTENSIONS:
        shown = extension or "(none)"
        raise UnsupportedFileTypeError(
            f"Unsupported file type {shown}. Please upload a PDF or DOCX file."
        )

    if extension == ".pdf":
        # The PDF spec allows a little junk before the header, so check the first 1 KB.
        if b"%PDF" not in content[:1024]:
            raise InvalidFileError("The file is named .pdf but its contents are not a PDF.")
        text = _extract_pdf_text(content)
    else:
        if not content.startswith(b"PK"):
            raise InvalidFileError("The file is named .docx but its contents are not a DOCX.")
        text = _extract_docx_text(content)

    if not text.strip():
        raise NoTextFoundError(
            "No readable text was found in this file. If it is a scanned image, "
            "please upload a text-based PDF or a DOCX instead (OCR is not supported yet)."
        )
    return text


def _extract_pdf_text(content: bytes) -> str:
    try:
        from pypdf import PdfReader
    except ImportError as exc:
        raise RuntimeError(
            "The 'pypdf' package is not installed. Run: pip install -r requirements.txt"
        ) from exc

    try:
        reader = PdfReader(io.BytesIO(content))
        if reader.is_encrypted:
            raise InvalidFileError("This PDF is password-protected. Please upload an unprotected copy.")
        pages = list(reader.pages)[:MAX_PDF_PAGES]
        # extract_text() can return an empty string for image-only pages
        return "\n".join((page.extract_text() or "") for page in pages)
    except InvalidFileError:
        raise
    except Exception as exc:  # pypdf raises many different error types for broken files
        raise InvalidFileError("The PDF could not be read. The file may be corrupt.") from exc


def _extract_docx_text(content: bytes) -> str:
    try:
        from docx import Document  # the package is "python-docx" but imported as "docx"
    except ImportError as exc:
        raise RuntimeError(
            "The 'python-docx' package is not installed. Run: pip install -r requirements.txt"
        ) from exc

    try:
        document = Document(io.BytesIO(content))
        lines = [paragraph.text for paragraph in document.paragraphs]
        # Many resume templates put content in tables. Table text is added after the
        # paragraphs (a known limitation: the original position is not preserved).
        for table in document.tables:
            for row in table.rows:
                cells = [cell.text.strip() for cell in row.cells if cell.text.strip()]
                if cells:
                    lines.append(" | ".join(cells))
        return "\n".join(lines)
    except Exception as exc:
        raise InvalidFileError("The DOCX file could not be read. The file may be corrupt.") from exc
