from fastapi import APIRouter, Depends, Query, Response
from sqlalchemy.orm import Session

from app.api.deps import get_knowledge_provider, get_llm
from app.config import Settings, get_settings
from app.db.session import get_db
from app.schemas.interview import InterviewPrepRead
from app.services import interview_service as interview
from app.services.agent.knowledge_tools import KnowledgeProvider
from app.services.llm.base import LLMClient

router = APIRouter(prefix="/applications/{application_id}/interview-prep", tags=["interview"])


# Plain `def`: the workflow blocks on LLM calls, so FastAPI runs it in a worker thread.
@router.post("", response_model=InterviewPrepRead)
def generate_interview_prep(
    application_id: int,
    question_count: int | None = Query(default=None, ge=3, le=12, description="defaults to INTERVIEW_QUESTION_COUNT"),
    llm: LLMClient = Depends(get_llm),
    db: Session = Depends(get_db),
    knowledge_provider: KnowledgeProvider = Depends(get_knowledge_provider),
    settings: Settings = Depends(get_settings),
) -> InterviewPrepRead:
    """Generate (or regenerate) the interview prep pack for an application.

    Needs a saved job match on the application. Uses 2 LLM calls (1 if none of your notes match anything).
    """
    return interview.generate_prep(
        db,
        llm,
        knowledge_provider,
        application_id,
        question_count or settings.interview_question_count,
        settings.rag_min_score,
    )


@router.get("", response_model=InterviewPrepRead)
def get_interview_prep(application_id: int, db: Session = Depends(get_db)) -> InterviewPrepRead:
    """The saved pack, with no LLM call."""
    return interview.get_prep(db, application_id)


@router.delete("", status_code=204, response_class=Response)
def delete_interview_prep(application_id: int, db: Session = Depends(get_db)) -> Response:
    interview.delete_prep(db, application_id)
    return Response(status_code=204)
