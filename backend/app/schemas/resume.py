"""Pydantic models describing a parsed resume.

These models are the CONTRACT between us and the LLM: whatever JSON the model
returns must fit these shapes, or validation fails and we retry.

Required fields have no default. Optional fields default to None / an empty list.
Dates are plain strings because resumes write them in many formats ("Jan 2021", "Present").
"""

from pydantic import BaseModel, ConfigDict, Field


class Experience(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    company: str
    title: str
    start_date: str | None = None
    end_date: str | None = None
    highlights: list[str] = Field(default_factory=list)


class Education(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    institution: str
    degree: str | None = None
    field_of_study: str | None = None
    graduation_year: int | None = None


class ParsedResume(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    full_name: str = Field(min_length=1)
    email: str | None = None
    phone: str | None = None
    location: str | None = None
    summary: str | None = None
    # No defaults on these three: the model must include them (use [] if there are none).
    skills: list[str]
    experience: list[Experience]
    education: list[Education]


class ResumeParseResponse(BaseModel):
    """What POST /resumes/parse returns."""

    filename: str
    characters_extracted: int
    text_truncated: bool  # True if the resume was too long and the end was cut off
    text_preview: str  # first part of the cleaned text, so you can see what the parser saw
    parsed: ParsedResume
