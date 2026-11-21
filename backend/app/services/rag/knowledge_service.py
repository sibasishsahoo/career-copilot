"""The knowledge base operations: add, list, view, delete and search documents.

Plain functions that receive their dependencies (the vector store and the embedder) as arguments.
That is "dependency injection": the same code runs against Chroma + the real model in production
and against an in-memory store + a fake embedder in tests. No HTTP and no pydantic in here.
"""

import uuid
from datetime import datetime, timezone

from app.services.rag.chunker import chunk_text, normalize_text
from app.services.rag.embedder import Embedder
from app.services.rag.errors import DocumentNotFoundError, EmbeddingError, EmptyDocumentError
from app.services.rag.models import DocumentInfo, SearchHit, StoredChunk
from app.services.rag.vector_store import VectorStore


def embedding_text(title: str, chunk: str) -> str:
    """What we actually embed for a chunk: the title plus the chunk.

    A chunk from the middle of a note often lacks context ("We cut it to 12 minutes"). Putting
    the title in front lets "Faster deployments: We cut it to 12 minutes" match a question about
    deployments. The title is only used for the embedding; the chunk text itself is stored as is.
    """
    return f"{title}\n{chunk}"


def add_document(
    store: VectorStore,
    embedder: Embedder,
    title: str,
    text: str,
    chunk_size: int,
    overlap: int,
) -> DocumentInfo:
    normalized = normalize_text(text)
    pieces = chunk_text(normalized, chunk_size, overlap)  # 1. chunk
    if not pieces:
        raise EmptyDocumentError("The document has no text to index.")

    clean_title = title.strip() or "Untitled"
    doc_id = uuid.uuid4().hex
    created_at = datetime.now(timezone.utc).isoformat()
    chunks = [
        StoredChunk(
            id=f"{doc_id}:{index}",
            doc_id=doc_id,
            title=clean_title,
            index=index,
            text=piece,
            created_at=created_at,
            doc_chars=len(normalized),
        )
        for index, piece in enumerate(pieces)
    ]

    vectors = embedder.embed([embedding_text(chunk.title, chunk.text) for chunk in chunks])  # 2. embed
    if len(vectors) != len(chunks):
        raise EmbeddingError("The embedding model returned the wrong number of vectors.")

    store.add(chunks, vectors)  # 3. store (only after embedding succeeded, so a failure saves nothing)
    return DocumentInfo(doc_id, clean_title, len(chunks), len(normalized), created_at)


def list_documents(store: VectorStore) -> list[DocumentInfo]:
    """Newest first."""
    return sorted(store.list_documents(), key=lambda info: info.created_at, reverse=True)


def get_document(store: VectorStore, doc_id: str) -> tuple[DocumentInfo, list[StoredChunk]]:
    chunks = store.get_document_chunks(doc_id)
    if not chunks:
        raise DocumentNotFoundError(f"Document {doc_id} was not found.")
    first = chunks[0]
    info = DocumentInfo(doc_id, first.title, len(chunks), first.doc_chars, first.created_at)
    return info, chunks


def delete_document(store: VectorStore, doc_id: str) -> int:
    removed = store.delete_document(doc_id)
    if removed == 0:
        raise DocumentNotFoundError(f"Document {doc_id} was not found.")
    return removed


def search_chunks(
    store: VectorStore,
    embedder: Embedder,
    query: str,
    k: int,
    min_score: float = -1.0,
) -> list[SearchHit]:
    """Retrieval: embed the question, ask the store for its k nearest chunks, drop weak matches.

    The question must be embedded by the SAME model that embedded the documents, otherwise the
    two vectors live in different "spaces" and the comparison is meaningless.
    """
    if not query.strip():
        raise ValueError("The query is empty.")
    vectors = embedder.embed([query.strip()])
    if len(vectors) != 1:
        raise EmbeddingError("The embedding model returned the wrong number of vectors.")
    hits = store.search(vectors[0], k)
    return [hit for hit in hits if hit.score >= min_score]
