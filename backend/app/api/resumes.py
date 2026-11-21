from fastapi import APIRouter, Depends, File, UploadFile

from app.api.deps import get_llm
from app.schemas.resume import ResumeParseResponse
from app.services.llm.base import LLMClient
from app.services.resume.cleaner import clean_text
from app.services.resume.extractor import MAX_UPLOAD_BYTES, extract_text, read_limited
from app.services.resume.parser import MAX_RESUME_CHARS, parse_resume_text

router = APIRouter(prefix="/resumes", tags=["resumes"])

PREVIEW_CHARS = 500


# Plain `def` again: file reading and the LLM call both block, so FastAPI runs this in a thread.
@router.post("/parse", response_model=ResumeParseResponse)
def parse_resume(
    file: UploadFile = File(...),
    llm: LLMClient = Depends(get_llm),
) -> ResumeParseResponse:
    filename = file.filename or ""

    content = read_limited(file.file, MAX_UPLOAD_BYTES)  # 1. size check
    raw_text = extract_text(filename, content)  # 2. type check + text extraction
    text = clean_text(raw_text)  # 3. tidy up
    parsed = parse_resume_text(llm, text)  # 4. LLM -> validated ParsedResume

    return ResumeParseResponse(
        filename=filename,
        characters_extracted=len(text),
        text_truncated=len(text) > MAX_RESUME_CHARS,
        text_preview=text[:PREVIEW_CHARS],
        parsed=parsed,
    )
