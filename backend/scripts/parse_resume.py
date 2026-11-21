"""Run the full resume pipeline on a local file using the REAL LLM provider.

Run from the backend/ folder:   python -m scripts.parse_resume path/to/resume.pdf
Tip: use a fake or anonymized resume while on the Gemini free tier.
"""

import sys
from pathlib import Path

from app.config import get_settings
from app.services.llm.base import LLMError
from app.services.llm.factory import get_llm_client
from app.services.resume.cleaner import clean_text
from app.services.resume.errors import ResumeError
from app.services.resume.extractor import MAX_UPLOAD_BYTES, extract_text, read_limited
from app.services.resume.parser import parse_resume_text


def main() -> int:
    if len(sys.argv) != 2:
        print("Usage: python -m scripts.parse_resume path/to/resume.pdf|docx")
        return 1
    path = Path(sys.argv[1])

    try:
        with path.open("rb") as handle:
            content = read_limited(handle, MAX_UPLOAD_BYTES)
        text = clean_text(extract_text(path.name, content))
        print(f"Extracted {len(text)} characters. Calling the LLM...\n")
        parsed = parse_resume_text(get_llm_client(get_settings()), text)
    except (ResumeError, LLMError, OSError) as exc:
        print(f"FAILED: {exc}")
        return 1

    print(parsed.model_dump_json(indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
