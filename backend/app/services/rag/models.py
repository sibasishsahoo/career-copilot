"""Plain data classes shared by every part of the RAG pipeline (no third-party packages)."""

from dataclasses import dataclass


@dataclass(frozen=True)
class StoredChunk:
    """One piece of a document, as kept in the vector store."""

    id: str  # "<doc_id>:<index>" - unique per chunk
    doc_id: str
    title: str
    index: int  # position of this chunk inside its document (0, 1, 2, ...)
    text: str
    created_at: str  # ISO 8601 UTC timestamp of when the document was added
    doc_chars: int  # length of the whole document (same for all of its chunks)


@dataclass(frozen=True)
class SearchHit:
    chunk: StoredChunk
    score: float  # cosine similarity: 1.0 = same direction, 0 = unrelated, higher is better


@dataclass(frozen=True)
class DocumentInfo:
    doc_id: str
    title: str
    chunk_count: int
    char_count: int
    created_at: str
