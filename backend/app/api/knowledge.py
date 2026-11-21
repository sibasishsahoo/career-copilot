from fastapi import APIRouter, Depends, Response

from app.api.deps import get_embedder, get_llm, get_vector_store
from app.config import Settings, get_settings
from app.schemas.knowledge import (
    AskRequest,
    AskResponse,
    ChunkRead,
    DocumentCreate,
    DocumentDetail,
    DocumentSummary,
    SearchRequest,
    SearchResponse,
    SearchResult,
)
from app.services.llm.base import LLMClient
from app.services.rag import knowledge_service as knowledge
from app.services.rag.answerer import answer_question
from app.services.rag.citations import NOT_FOUND_ANSWER
from app.services.rag.embedder import Embedder
from app.services.rag.models import DocumentInfo, SearchHit
from app.services.rag.vector_store import VectorStore

router = APIRouter(prefix="/knowledge", tags=["knowledge"])


def _summary(info: DocumentInfo) -> DocumentSummary:
    return DocumentSummary(
        id=info.doc_id,
        title=info.title,
        chunk_count=info.chunk_count,
        char_count=info.char_count,
        created_at=info.created_at,
    )


def _results(hits: list[SearchHit]) -> list[SearchResult]:
    return [
        SearchResult(
            rank=rank,
            score=round(hit.score, 4),
            doc_id=hit.chunk.doc_id,
            title=hit.chunk.title,
            chunk_index=hit.chunk.index,
            text=hit.chunk.text,
        )
        for rank, hit in enumerate(hits, start=1)
    ]


# Plain `def` routes: embedding and LLM calls block, so FastAPI runs them in worker threads.

@router.post("/documents", response_model=DocumentSummary, status_code=201)
def add_document(
    body: DocumentCreate,
    store: VectorStore = Depends(get_vector_store),
    embedder: Embedder = Depends(get_embedder),
    settings: Settings = Depends(get_settings),
) -> DocumentSummary:
    """Chunk a note, embed each chunk, and save it to the vector database."""
    info = knowledge.add_document(
        store, embedder, body.title, body.text, settings.rag_chunk_size, settings.rag_chunk_overlap
    )
    return _summary(info)


@router.get("/documents", response_model=list[DocumentSummary])
def list_documents(store: VectorStore = Depends(get_vector_store)) -> list[DocumentSummary]:
    return [_summary(info) for info in knowledge.list_documents(store)]


@router.get("/documents/{doc_id}", response_model=DocumentDetail)
def get_document(doc_id: str, store: VectorStore = Depends(get_vector_store)) -> DocumentDetail:
    """Shows how a document was split, which is useful when tuning the chunk size."""
    info, chunks = knowledge.get_document(store, doc_id)
    return DocumentDetail(
        **_summary(info).model_dump(),
        chunks=[ChunkRead(index=chunk.index, text=chunk.text) for chunk in chunks],
    )


@router.delete("/documents/{doc_id}", status_code=204, response_class=Response)
def delete_document(doc_id: str, store: VectorStore = Depends(get_vector_store)) -> Response:
    knowledge.delete_document(store, doc_id)
    return Response(status_code=204)


@router.post("/search", response_model=SearchResponse)
def search(
    body: SearchRequest,
    store: VectorStore = Depends(get_vector_store),
    embedder: Embedder = Depends(get_embedder),
) -> SearchResponse:
    """Retrieval only, with no LLM: see exactly which chunks match and with what score."""
    hits = knowledge.search_chunks(store, embedder, body.query, body.k)
    return SearchResponse(query=body.query, results=_results(hits))


@router.post("/ask", response_model=AskResponse)
def ask(
    body: AskRequest,
    llm: LLMClient = Depends(get_llm),
    store: VectorStore = Depends(get_vector_store),
    embedder: Embedder = Depends(get_embedder),
    settings: Settings = Depends(get_settings),
) -> AskResponse:
    """The full RAG flow: retrieve the best chunks, then let the LLM answer from them."""
    min_score = settings.rag_min_score if settings.rag_min_score is not None else embedder.default_min_score
    hits = knowledge.search_chunks(store, embedder, body.question, body.k, min_score)

    if not hits:
        # Nothing relevant: skip the LLM. It saves a call and removes any chance of a made-up answer.
        return AskResponse(
            question=body.question,
            answer=NOT_FOUND_ANSWER,
            grounded=False,
            sources_used=[],
            sources=[],
            used_llm=False,
        )

    answer = answer_question(llm, body.question, hits)
    return AskResponse(
        question=body.question,
        answer=answer.text,
        grounded=answer.grounded,
        sources_used=answer.sources_used,
        sources=_results(hits),
        used_llm=True,
    )
