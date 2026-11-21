"""The LLM's only job in matching: turn the computed skill gaps into readable advice."""

from app.schemas.job import JobAnalysis, SkillComparison, SuggestionList
from app.schemas.resume import ParsedResume
from app.services.job.prompts import (
    SUGGESTIONS_SYSTEM_PROMPT,
    build_resume_digest,
    build_suggestions_prompt,
)
from app.services.llm.base import LLMClient
from app.services.llm.structured import generate_structured

MAX_RETRIES = 1


def generate_suggestions(
    llm: LLMClient,
    resume: ParsedResume,
    job: JobAnalysis,
    comparison: SkillComparison,
) -> list[str]:
    missing_required = comparison.required.missing
    missing_preferred = comparison.preferred.missing

    # Nothing is missing -> nothing to advise. Skipping the call saves time, money and rate limit.
    if not missing_required and not missing_preferred:
        return []

    digest = build_resume_digest(
        skills=resume.skills,
        experiences=[(e.title, e.company, e.highlights) for e in resume.experience],
    )
    prompt = build_suggestions_prompt(
        job_title=job.job_title,
        matched_required=[hit.skill for hit in comparison.required.matched],
        missing_required=missing_required,
        missing_preferred=missing_preferred,
        resume_digest=digest,
    )
    result = generate_structured(
        llm=llm,
        prompt=prompt,
        schema=SuggestionList,
        system_prompt=SUGGESTIONS_SYSTEM_PROMPT,
        max_retries=MAX_RETRIES,
    )
    return result.suggestions
