"""Assembles the agent's complete toolbox. To give the agent a new ability you write a Tool
(see knowledge_tools.py) and add it to the list below - nothing else in the agent changes."""

from sqlalchemy.orm import Session

from app.services.agent.knowledge_tools import KnowledgeProvider, build_search_knowledge_tool
from app.services.agent.tools import ToolRegistry
from app.services.agent.tracker_tools import build_get_application_tool, build_list_applications_tool


def build_registry(db: Session, knowledge_provider: KnowledgeProvider, rag_min_score: float | None) -> ToolRegistry:
    return ToolRegistry(
        [
            build_search_knowledge_tool(knowledge_provider, rag_min_score),
            build_list_applications_tool(db),
            build_get_application_tool(db),
        ]
    )
