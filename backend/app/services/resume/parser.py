"""Step 4 of the pipeline: resume text -> ParsedResume, using the LLM.

Resume-specific logic only: the prompt and the schema. The generic "ask, extract JSON,
validate, retry" machinery lives in services/llm/structured.py, and the actual
provider (Gemini etc.) is hidden behind LLMClient. Three layers, each replaceable:

    parser.py      what to ask (resume prompt + ParsedResume schema)
    structured.py  how to get reliable JSON (extract, validate, retry)
    LLMClient      who answers (Gemini / Anthropic / OpenAI)
"""

from app.schemas.resume import ParsedResume
from app.services.llm.base import LLMClient
from app.services.llm.structured import generate_structured
from app.services.resume.errors import NoTextFoundError
from app.services.resume.prompts import SYSTEM_PROMPT, build_user_prompt

# Longer resumes are cut off to keep cost and latency bounded (~20k chars is about 8 pages).
MAX_RESUME_CHARS = 20_000
MAX_RETRIES = 1  # 1 first try + at most 1 retry = 2 LLM calls worst case


def parse_resume_text(llm: LLMClient, resume_text: str) -> ParsedResume:
    text = resume_text.strip()
    if not text:
        raise NoTextFoundError("The resume text is empty.")
    text = text[:MAX_RESUME_CHARS]

    return generate_structured(
        llm=llm,
        prompt=build_user_prompt(text),
        schema=ParsedResume,
        system_prompt=SYSTEM_PROMPT,
        max_retries=MAX_RETRIES,
    )
