"""Builds the embedder and vector store named in the settings. Results are cached, because loading
a model or opening a database is slow and should happen once per program run."""

from functools import lru_cache

from app.services.rag.embedder import Embedder, HashingEmbedder, LocalEmbedder
from app.services.rag.errors import EmbeddingError, VectorStoreError
from app.services.rag.vector_store import InMemoryVectorStore, VectorStore


@lru_cache
def build_embedder(kind: str) -> Embedder:
    name = kind.strip().lower()
    if name == "local":
        return LocalEmbedder()
    if name == "hashing":
        return HashingEmbedder()
    raise EmbeddingError(f"Unknown RAG_EMBEDDER '{kind}'. Supported values: local, hashing.")


@lru_cache
def build_vector_store(kind: str, chroma_path: str, embedder_name: str) -> VectorStore:
    name = kind.strip().lower()
    if name == "memory":
        return InMemoryVectorStore()
    if name == "chroma":
        from app.services.rag.chroma_store import ChromaVectorStore

        # One collection PER EMBEDDER: vectors from different models are not comparable (they can
        # even have different lengths), so they must never be mixed. Switching RAG_EMBEDDER simply
        # opens a different, separate collection; your earlier notes stay safe in the old one.
        return ChromaVectorStore(path=chroma_path, collection_name=f"career_knowledge_{embedder_name}")
    raise VectorStoreError(f"Unknown RAG_STORE '{kind}'. Supported values: chroma, memory.")
