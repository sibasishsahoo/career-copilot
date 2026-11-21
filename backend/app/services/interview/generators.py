"""The two LLM steps of the workflow, as plain callables the pipeline can receive.

Each one builds its prompts (prompts.py), asks the model for JSON, validates it against a Pydantic
schema and retries once with the exact problem - all through generate_structured from Phase 2.
"""

from app.schemas.interview import GeneratedAnswers, QuestionSet
from app.services.interview.models import DraftedAnswer, DraftingInput, JobContext, Question, QuestionPlan
from app.services.interview.prompts import build_drafting_prompts, build_question_prompts
from app.services.llm.base import LLMClient
from app.services.llm.structured import generate_structured


class LLMQuestionGenerator:
    """Step 1: job context -> interview questions."""

    def __init__(self, llm: LLMClient, max_retries: int = 1) -> None:
        self._llm = llm
        self._max_retries = max_retries

    def __call__(self, job: JobContext, count: int) -> QuestionPlan:
        system, user = build_question_prompts(job, count)
        parsed = generate_structured(
            self._llm, user, QuestionSet, system_prompt=system, max_retries=self._max_retries
        )
        return QuestionPlan(
            questions=[
                Question(0, q.text, q.category, q.why_asked, q.skill)  # the pipeline numbers them
                for q in parsed.questions
            ],
            questions_to_ask=list(parsed.questions_to_ask),
        )


class LLMAnswerDrafter:
    """Step 2: questions + the notes found for them -> answer outlines."""

    def __init__(self, llm: LLMClient, max_retries: int = 1) -> None:
        self._llm = llm
        self._max_retries = max_retries

    def __call__(self, drafting: DraftingInput) -> list[DraftedAnswer]:
        system, user = build_drafting_prompts(drafting)
        parsed = generate_structured(
            self._llm, user, GeneratedAnswers, system_prompt=system, max_retries=self._max_retries
        )
        return [
            DraftedAnswer(a.question_id, a.fits, a.outline, list(a.sources_used)) for a in parsed.answers
        ]
