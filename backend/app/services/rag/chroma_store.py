"""The real vector database: Chroma, saved to a folder on disk.

We calculate the embeddings ourselves (embedder.py) and hand them to Chroma, so you can see every
step. Chroma then does two jobs: it stores chunk + vector + metadata, and it finds nearest
neighbours quickly using an HNSW index.

Written against the chromadb 1.x Python API; see tests/test_chroma_store.py, which checks the
assumptions below (especially that cosine distance converts to similarity as 1 - distance).
"""

from app.services.rag.errors import VectorStoreError
from app.services.rag.models import DocumentInfo, SearchHit, StoredChunk
from app.services.rag.vector_store import VectorStore, group_into_documents


def _to_chunk(chunk_id: str, text: str, metadata: dict) -> StoredChunk:
    return StoredChunk(
        id=chunk_id,
        doc_id=str(metadata["doc_id"]),
        title=str(metadata["title"]),
        index=int(metadata["chunk_index"]),
        text=text,
        created_at=str(metadata["created_at"]),
        doc_chars=int(metadata["doc_chars"]),
    )


class ChromaVectorStore(VectorStore):
    def __init__(self, path: str, collection_name: str) -> None:
        try:
            import chromadb
        except ImportError as exc:
            raise VectorStoreError(
                "The 'chromadb' package is not installed. Run: pip install -r requirements.txt"
            ) from exc
        try:
            client = chromadb.PersistentClient(path=path)
            self._collection = client.get_or_create_collection(
                name=collection_name,
                embedding_function=None,  # we supply the vectors ourselves
                metadata={"hnsw:space": "cosine"},  # rank by cosine similarity, like our own math
            )
        except Exception as exc:
            raise VectorStoreError(f"Could not open the Chroma database at {path}: {exc}") from exc

    def add(self, chunks: list[StoredChunk], embeddings: list[list[float]]) -> None:
        if len(chunks) != len(embeddings):
            raise ValueError("chunks and embeddings must have the same length.")
        if not chunks:
            return
        try:
            self._collection.add(
                ids=[chunk.id for chunk in chunks],
                embeddings=embeddings,
                documents=[chunk.text for chunk in chunks],
                metadatas=[
                    {
                        "doc_id": chunk.doc_id,
                        "title": chunk.title,
                        "chunk_index": chunk.index,
                        "created_at": chunk.created_at,
                        "doc_chars": chunk.doc_chars,
                    }
                    for chunk in chunks
                ],
            )
        except Exception as exc:
            raise VectorStoreError(f"Could not save to the vector database: {exc}") from exc

    def search(self, query_embedding: list[float], k: int) -> list[SearchHit]:
        try:
            available = self._collection.count()
            if k <= 0 or available == 0:
                return []
            result = self._collection.query(
                query_embeddings=[query_embedding],
                n_results=min(k, available),
                include=["documents", "metadatas", "distances"],
            )
        except Exception as exc:
            raise VectorStoreError(f"Vector search failed: {exc}") from exc

        hits = []
        for chunk_id, text, metadata, distance in zip(
            result["ids"][0], result["documents"][0], result["metadatas"][0], result["distances"][0]
        ):
            # In "cosine" space Chroma reports distance = 1 - cosine similarity.
            hits.append(SearchHit(_to_chunk(chunk_id, text, metadata), 1.0 - float(distance)))
        return hits

    def _all_chunks(self, **filters) -> list[StoredChunk]:
        try:
            result = self._collection.get(include=["documents", "metadatas"], **filters)
        except Exception as exc:
            raise VectorStoreError(f"Could not read from the vector database: {exc}") from exc
        return [
            _to_chunk(chunk_id, text, metadata)
            for chunk_id, text, metadata in zip(result["ids"], result["documents"], result["metadatas"])
        ]

    def list_documents(self) -> list[DocumentInfo]:
        return group_into_documents(self._all_chunks())

    def get_document_chunks(self, doc_id: str) -> list[StoredChunk]:
        chunks = self._all_chunks(where={"doc_id": doc_id})
        return sorted(chunks, key=lambda chunk: chunk.index)

    def delete_document(self, doc_id: str) -> int:
        removed = len(self._all_chunks(where={"doc_id": doc_id}))
        if removed:
            try:
                self._collection.delete(where={"doc_id": doc_id})
            except Exception as exc:
                raise VectorStoreError(f"Could not delete from the vector database: {exc}") from exc
        return removed

    def count(self) -> int:
        try:
            return int(self._collection.count())
        except Exception as exc:
            raise VectorStoreError(f"Could not count chunks: {exc}") from exc
