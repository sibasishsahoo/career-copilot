"""Plain data classes for the interview-preparation workflow (no third-party packages)."""

from dataclasses import dataclass, field


@dataclass(frozen=True)
class JobContext:
    """Everything known about the job. It comes from the application and its saved match - never from the resume."""

    application_id: int
    company: str
    job_title: str
    job_description: str
    score: int | None
    matched_skills: list[str]  # job skills the candidate already shows
    missing_skills: list[str]  # job skills the candidate lacks


@dataclass(frozen=True)
class Question:
    number: int  # 1, 2, 3... assigned by the pipeline
    text: str
    category: str  # behavioral | technical | role | gap
    why_asked: str
    skill: str | None


@dataclass(frozen=True)
class QuestionPlan:
    """Output of the first LLM step."""

    questions: list[Question]
    questions_to_ask: list[str]  # questions the candidate can ask the interviewer


@dataclass(frozen=True)
class Source:
    """One passage of the user's notes, numbered so the LLM can cite it as [number]."""

    number: int
    title: str
    text: str


@dataclass(frozen=True)
class QuestionSources:
    question: Question
    source_numbers: list[int]  # the numbered sources the LLM may use for THIS question


@dataclass(frozen=True)
class DraftingInput:
    """Input of the second LLM step."""

    job: JobContext
    questions: list[QuestionSources]
    sources: list[Source]


@dataclass(frozen=True)
class DraftedAnswer:
    """Output of the second LLM step, for one question."""

    question_number: int
    fits: bool  # does a real experience in the sources answer this question?
    outline: str
    sources_used: list[int]


@dataclass(frozen=True)
class PrepItem:
    number: int
    question: str
    category: str
    why_asked: str
    skill: str | None
    story_found: bool
    answer_outline: str | None
    sources: list[str]  # titles of the notes the outline is built from
    note: str | None  # why there is no story, when story_found is False


@dataclass(frozen=True)
class Coverage:
    total: int
    with_story: int
    without_story: list[int] = field(default_factory=list)  # question numbers that need a note


@dataclass(frozen=True)
class PrepPack:
    items: list[PrepItem]
    questions_to_ask: list[str]
    coverage: Coverage
