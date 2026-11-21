from dataclasses import asdict

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.deps import get_knowledge_provider, get_llm
from app.config import Settings, get_settings
from app.db.session import get_db
from app.schemas.agent import AgentAskRequest, AgentAskResponse, AgentStepRead
from app.services.agent.builtin_tools import build_registry
from app.services.agent.decider import LLMDecider
from app.services.agent.knowledge_tools import KnowledgeProvider
from app.services.agent.loop import run_agent
from app.services.llm.base import LLMClient

router = APIRouter(prefix="/agent", tags=["agent"])


# Plain `def`: the loop blocks on LLM and database calls, so FastAPI runs it in a worker thread.
@router.post("/ask", response_model=AgentAskResponse)
def ask_agent(
    body: AgentAskRequest,
    llm: LLMClient = Depends(get_llm),
    db: Session = Depends(get_db),
    knowledge_provider: KnowledgeProvider = Depends(get_knowledge_provider),
    settings: Settings = Depends(get_settings),
) -> AgentAskResponse:
    """Ask a question. The agent may look things up in your tracker and notes (read-only) before answering.

    Each step costs one LLM call, so one question uses roughly 2 to 4 calls: mind the free-tier limits.
    """
    registry = build_registry(db, knowledge_provider, settings.rag_min_score)
    result = run_agent(LLMDecider(llm), registry, body.question, settings.agent_max_steps)

    return AgentAskResponse(
        question=body.question,
        answer=result.answer,
        stopped_reason=result.stopped_reason,
        steps=[AgentStepRead(**asdict(step)) for step in result.steps],
    )
