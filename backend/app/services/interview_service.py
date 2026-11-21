"""Interview preparation for one application: load -> run the workflow -> save.

This is the only interview file that touches the database. It receives the LLM and the knowledge
base as arguments, exactly like the other services, so tests can supply fakes.
"""

from dataclasses import asdict

from sqlalchemy.orm import Session

from app.db.types import utcnow
from app.models.application import Application
from app.models.interview_prep import InterviewPrep
from app.schemas.interview import InterviewPrepRead
from app.services import application_service as tracker
from app.services.agent.knowledge_tools import KnowledgeProvider
from app.services.application_service import TrackerNotFoundError
from app.services.interview.errors import NoSavedMatchError
from app.services.interview.generators import LLMAnswerDrafter, LLMQuestionGenerator
from app.services.interview.models import JobContext
from app.services.interview.pipeline import PER_QUESTION_K, build_prep
from app.services.llm.base import LLMClient
from app.services.rag import knowledge_service as knowledge

MIN_QUESTIONS, MAX_QUESTIONS = 3, 12


class InterviewPrepNotFoundError(TrackerNotFoundError):
    """The application exists but has no prep pack yet (HTTP 404)."""


def _job_context(application: Application) -> JobContext:
    snapshot = application.match_snapshot
    if snapshot is None:
        raise NoSavedMatchError(
            f"Application {application.id} has no saved job match, so there is no job description to "
            "prepare from. Analyze the job in the Match tool and save the match to this application first."
        )
    return JobContext(
        application_id=application.id,
        company=application.company,
        job_title=application.job_title,
        job_description=snapshot.job_description,
        score=snapshot.score,
        matched_skills=[entry["skill"] for entry in snapshot.matched_skills],
        missing_skills=[entry["skill"] for entry in snapshot.missing_skills],
    )


def to_read(application: Application, row: InterviewPrep) -> InterviewPrepRead:
    return InterviewPrepRead(
        application_id=application.id,
        company=application.company,
        job_title=application.job_title,
        generated_at=row.generated_at.isoformat(),
        **row.content,
    )


def generate_prep(
    db: Session,
    llm: LLMClient,
    knowledge_provider: KnowledgeProvider,
    application_id: int,
    question_count: int,
    rag_min_score: float | None,
) -> InterviewPrepRead:
    application = tracker.get_application(db, application_id)  # 404 if it does not exist
    job = _job_context(application)  # 409 if there is no saved match

    # Open the knowledge base BEFORE any LLM call: if it is unavailable, fail without spending a call.
    store, embedder = knowledge_provider()
    threshold = rag_min_score if rag_min_score is not None else embedder.default_min_score

    def search(query: str):
        return knowledge.search_chunks(store, embedder, query, PER_QUESTION_K, threshold)

    pack = build_prep(
        job,
        LLMQuestionGenerator(llm),
        search,
        LLMAnswerDrafter(llm),
        max(MIN_QUESTIONS, min(question_count, MAX_QUESTIONS)),
    )

    content = asdict(pack)  # dataclasses -> plain dicts/lists, ready for the JSON column
    if application.interview_prep is None:
        application.interview_prep = InterviewPrep(content=content, generated_at=utcnow())
    else:  # replace the previous pack
        application.interview_prep.content = content
        application.interview_prep.generated_at = utcnow()
    db.commit()
    return to_read(application, application.interview_prep)


def _existing_prep(db: Session, application_id: int) -> tuple[Application, InterviewPrep]:
    application = tracker.get_application(db, application_id)
    if application.interview_prep is None:
        raise InterviewPrepNotFoundError(
            f"Application {application_id} has no interview prep yet. "
            f"Generate it with POST /applications/{application_id}/interview-prep."
        )
    return application, application.interview_prep


def get_prep(db: Session, application_id: int) -> InterviewPrepRead:
    application, row = _existing_prep(db, application_id)
    return to_read(application, row)


def delete_prep(db: Session, application_id: int) -> None:
    application, _ = _existing_prep(db, application_id)
    application.interview_prep = None  # delete-orphan removes the row
    db.commit()
