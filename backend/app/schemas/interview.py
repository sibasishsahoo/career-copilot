"""Pydantic schemas for interview preparation."""

from typing import Literal

from pydantic import BaseModel, Field, model_validator


# ---------- what the LLM must return in step 1 (the questions) ----------

class GeneratedQuestion(BaseModel):
    text: str = Field(min_length=10, max_length=400)
    category: Literal["behavioral", "technical", "role", "gap"]
    why_asked: str = Field(default="", max_length=400)
    skill: str | None = Field(default=None, max_length=100)


class QuestionSet(BaseModel):
    questions: list[GeneratedQuestion] = Field(min_length=1, max_length=15)
    questions_to_ask: list[str] = Field(default_factory=list, max_length=10)


# ---------- what the LLM must return in step 2 (the answer outlines) ----------

class GeneratedAnswer(BaseModel):
    question_id: int
    fits: bool
    outline: str = ""
    sources_used: list[int] = Field(default_factory=list)

    @model_validator(mode="after")
    def an_outline_is_required_when_the_story_fits(self) -> "GeneratedAnswer":
        if self.fits and not self.outline.strip():
            raise ValueError('"outline" is required when "fits" is true')
        return self


class GeneratedAnswers(BaseModel):
    answers: list[GeneratedAnswer]


# ---------- the API response (also the shape stored in the database) ----------

class PrepItemRead(BaseModel):
    number: int
    question: str
    category: str
    why_asked: str
    skill: str | None
    story_found: bool  # False = no note of yours really answers this question (see `note`)
    answer_outline: str | None
    sources: list[str]  # titles of the notes the outline is built from
    note: str | None


class CoverageRead(BaseModel):
    total: int
    with_story: int
    without_story: list[int]  # question numbers you still need a note for


class InterviewPrepRead(BaseModel):
    application_id: int
    company: str
    job_title: str
    generated_at: str
    items: list[PrepItemRead]
    questions_to_ask: list[str]
    coverage: CoverageRead
