"""Step 3 of RAG: store vectors and find the nearest ones.

`VectorStore` is the interface. `InMemoryVectorStore` below is the simplest possible
implementation - read it first to understand what a vector database actually does:
"compare the question's vector with every stored vector and return the best matches".
`ChromaVectorStore` (chroma_store.py) does the same job, but saves to disk and uses a faster
index (HNSW) that does not have to look at every vector.
"""

from abc import ABC, abstractmethod

from app.services.rag.models import DocumentInfo, SearchHit, StoredChunk
from app.services.rag.similarity import cosine_similarity


class VectorStore(ABC):
    @abstractmethod
    def add(self, chunks: list[StoredChunk], embeddings: list[list[float]]) -> None:
        """Store chunks together with their vectors (same order, same length)."""

    @abstractmethod
    def search(self, query_embedding: list[float], k: int) -> list[SearchHit]:
        """Return the k most similar chunks, best first."""

    @abstractmethod
    def list_documents(self) -> list[DocumentInfo]:
        """One entry per document (its chunks grouped together)."""

    @abstractmethod
    def get_document_chunks(self, doc_id: str) -> list[StoredChunk]:
        """All chunks of one document in reading order (empty list if unknown)."""

    @abstractmethod
    def delete_document(self, doc_id: str) -> int:
        """Delete a document's chunks. Returns how many chunks were removed."""

    @abstractmethod
    def count(self) -> int:
        """Total number of chunks stored."""


def group_into_documents(chunks: list[StoredChunk]) -> list[DocumentInfo]:
    """Shared helper: turn a flat list of chunks into one DocumentInfo per document."""
    grouped: dict[str, list[StoredChunk]] = {}
    for chunk in chunks:
        grouped.setdefault(chunk.doc_id, []).append(chunk)
    return [
        DocumentInfo(
            doc_id=doc_id,
            title=members[0].title,
            chunk_count=len(members),
            char_count=members[0].doc_chars,
            created_at=members[0].created_at,
        )
        for doc_id, members in grouped.items()
    ]


class InMemoryVectorStore(VectorStore):
    """Keeps everything in a Python dict. Data is lost when the program stops."""

    def __init__(self) -> None:
        self._items: dict[str, tuple[StoredChunk, list[float]]] = {}

    def add(self, chunks: list[StoredChunk], embeddings: list[list[float]]) -> None:
        if len(chunks) != len(embeddings):
            raise ValueError("chunks and embeddings must have the same length.")
        for chunk, vector in zip(chunks, embeddings):
            self._items[chunk.id] = (chunk, list(vector))

    def search(self, query_embedding: list[float], k: int) -> list[SearchHit]:
        if k <= 0:
            return []
        # Brute force: score EVERY stored vector. Fine for thousands of chunks.
        hits = [
            SearchHit(chunk, cosine_similarity(query_embedding, vector))
            for chunk, vector in self._items.values()
        ]
        # Best score first; doc and position break ties so the order is always the same.
        hits.sort(key=lambda hit: (-hit.score, hit.chunk.doc_id, hit.chunk.index))
        return hits[:k]

    def list_documents(self) -> list[DocumentInfo]:
        return group_into_documents([chunk for chunk, _ in self._items.values()])

    def get_document_chunks(self, doc_id: str) -> list[StoredChunk]:
        chunks = [chunk for chunk, _ in self._items.values() if chunk.doc_id == doc_id]
        return sorted(chunks, key=lambda chunk: chunk.index)

    def delete_document(self, doc_id: str) -> int:
        doomed = [chunk_id for chunk_id, (chunk, _) in self._items.items() if chunk.doc_id == doc_id]
        for chunk_id in doomed:
            del self._items[chunk_id]
        return len(doomed)

    def count(self) -> int:
        return len(self._items)
