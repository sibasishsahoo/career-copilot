"""Pydantic models for job analysis and resume-to-job matching."""

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from app.schemas.resume import ParsedResume

MIN_JOB_CHARS = 50  # shorter than this is not a real job description
MAX_JOB_CHARS = 15_000


# ---------- what the LLM must return when analyzing a job posting ----------

class JobAnalysis(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    job_title: str = Field(min_length=1)
    company: str | None = None
    location: str | None = None
    seniority: str | None = None
    employment_type: str | None = None
    # No defaults: the model must include these (use [] if there are none).
    required_skills: list[str]
    preferred_skills: list[str]
    responsibilities: list[str]
    min_years_experience: int | None = None


# ---------- what the LLM must return when writing suggestions ----------

class SuggestionList(BaseModel):
    suggestions: list[str] = Field(min_length=1)


# ---------- API request bodies ----------

class JobAnalyzeRequest(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    job_description: str = Field(min_length=MIN_JOB_CHARS, max_length=MAX_JOB_CHARS)


class JobMatchRequest(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    resume: ParsedResume  # paste the "parsed" object returned by POST /resumes/parse
    job_description: str = Field(min_length=MIN_JOB_CHARS, max_length=MAX_JOB_CHARS)


# ---------- API response ----------

class SkillMatch(BaseModel):
    skill: str
    found_in: Literal["skills_section", "experience_text"]


class SkillGroupResult(BaseModel):
    matched: list[SkillMatch]
    missing: list[str]


class SkillComparison(BaseModel):
    """The deterministic part of a match: computed by code, never by the LLM."""

    score: int = Field(ge=0, le=100)
    required: SkillGroupResult
    preferred: SkillGroupResult


class MatchResult(SkillComparison):
    job: JobAnalysis  # what the analyzer extracted, so you can see what it understood
    suggestions: list[str]  # the only LLM-written part (empty if nothing is missing)
