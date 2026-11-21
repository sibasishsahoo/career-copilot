from fastapi import APIRouter, Depends

from app.api.deps import get_llm
from app.schemas.job import JobAnalysis, JobAnalyzeRequest, JobMatchRequest, MatchResult
from app.services.job.analyzer import analyze_job
from app.services.job.matcher import compare_resume_to_job
from app.services.job.suggestions import generate_suggestions
from app.services.llm.base import LLMClient

router = APIRouter(prefix="/jobs", tags=["jobs"])


@router.post("/analyze", response_model=JobAnalysis)
def analyze(body: JobAnalyzeRequest, llm: LLMClient = Depends(get_llm)) -> JobAnalysis:
    """Extract structured data (title, skills, responsibilities...) from pasted job text."""
    return analyze_job(llm, body.job_description)


@router.post("/match", response_model=MatchResult)
def match(body: JobMatchRequest, llm: LLMClient = Depends(get_llm)) -> MatchResult:
    """Compare a parsed resume with a job description.

    Worst case this makes 4 LLM calls (2 steps x [1 try + 1 retry]); the usual case is 2.
    """
    job = analyze_job(llm, body.job_description)  # 1. LLM: text -> JobAnalysis
    comparison = compare_resume_to_job(body.resume, job)  # 2. CODE: matched/missing + score
    suggestions = generate_suggestions(llm, body.resume, job, comparison)  # 3. LLM: advice

    return MatchResult(**comparison.model_dump(), job=job, suggestions=suggestions)
