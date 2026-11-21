"""Job text -> JobAnalysis, using the LLM.

Exactly the same three-layer pattern as resume/parser.py: this file decides WHAT to ask
(prompt + schema), structured.py handles HOW to get reliable JSON, LLMClient is WHO answers.
`generate_structured` from Phase 2 is reused without any change.
"""

from app.schemas.job import MAX_JOB_CHARS, JobAnalysis
from app.services.job.errors import EmptyJobDescriptionError
from app.services.job.prompts import ANALYSIS_SYSTEM_PROMPT, build_analysis_prompt
from app.services.llm.base import LLMClient
from app.services.llm.structured import generate_structured
from app.services.resume.cleaner import clean_text  # same whitespace cleanup as for resumes

MAX_RETRIES = 1  # 1 first try + at most 1 retry


def analyze_job(llm: LLMClient, job_text: str) -> JobAnalysis:
    text = clean_text(job_text)
    if not text:
        raise EmptyJobDescriptionError("The job description is empty.")

    return generate_structured(
        llm=llm,
        prompt=build_analysis_prompt(text[:MAX_JOB_CHARS]),
        schema=JobAnalysis,
        system_prompt=ANALYSIS_SYSTEM_PROMPT,
        max_retries=MAX_RETRIES,
    )
