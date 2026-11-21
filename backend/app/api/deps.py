"""FastAPI dependencies: things a route needs, built for it by FastAPI.

Routes declare what they need with `Depends(...)`. In tests we can swap these
out (app.dependency_overrides) so no real API call is ever made.
"""

from fastapi import Depends

from app.config import Settings, get_settings
from app.services.llm.base import LLMClient
from app.services.llm.factory import get_llm_client
from app.services.agent.knowledge_tools import KnowledgeProvider
from app.services.rag.embedder import Embedder
from app.services.rag.factory import build_embedder, build_vector_store
from app.services.rag.vector_store import VectorStore


def get_llm(settings: Settings = Depends(get_settings)) -> LLMClient:
    return get_llm_client(settings)


def get_embedder(settings: Settings = Depends(get_settings)) -> Embedder:
    return build_embedder(settings.rag_embedder)


def get_vector_store(
    settings: Settings = Depends(get_settings),
    embedder: Embedder = Depends(get_embedder),
) -> VectorStore:
    return build_vector_store(settings.rag_store, settings.chroma_path, embedder.name)


def get_knowledge_provider(settings: Settings = Depends(get_settings)) -> KnowledgeProvider:
    """A function the agent calls only if it actually searches the notes (so a question about the
    tracker alone never loads the embedding model or opens Chroma)."""

    def provide() -> tuple[VectorStore, Embedder]:
        embedder = build_embedder(settings.rag_embedder)
        return build_vector_store(settings.rag_store, settings.chroma_path, embedder.name), embedder

    return provide
