"""The agent's window onto your career notes (Phase 6 RAG). Read-only."""

from collections.abc import Callable
from typing import Any

from app.services.agent.tools import Tool, ToolError, ToolParam
from app.services.rag import knowledge_service as knowledge
from app.services.rag.embedder import Embedder
from app.services.rag.errors import RagError
from app.services.rag.vector_store import VectorStore

# The agent gets the store and embedder through a function, called only when the tool is used.
# So a question that never touches the notes does not need the vector database or the model.
KnowledgeProvider = Callable[[], tuple[VectorStore, Embedder]]


def build_search_knowledge_tool(provider: KnowledgeProvider, min_score: float | None) -> Tool:
    def run(args: dict[str, Any]) -> dict[str, Any]:
        try:
            store, embedder = provider()
            threshold = min_score if min_score is not None else embedder.default_min_score
            hits = knowledge.search_chunks(store, embedder, args["query"], args["k"], threshold)
        except RagError as exc:
            raise ToolError(f"the knowledge base is unavailable: {exc}") from exc

        if not hits:
            return {"count": 0, "matches": [], "message": "No notes matched this query."}
        return {
            "count": len(hits),
            "matches": [
                {"note": hit.chunk.title, "score": round(hit.score, 3), "text": hit.chunk.text}
                for hit in hits
            ],
        }

    return Tool(
        name="search_knowledge",
        description=(
            "Search the user's own career notes (project write-ups, STAR stories, achievements) "
            "by meaning. Returns the best matching passages with their note titles."
        ),
        params=(
            ToolParam("query", "string", "what to look for, in plain words", max_length=500),
            ToolParam("k", "integer", "how many passages to return", required=False, default=3, minimum=1, maximum=5),
        ),
        run=run,
    )
