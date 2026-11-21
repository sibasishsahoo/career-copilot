"""Errors for the knowledge base (RAG). main.py maps each one to an HTTP status code."""


class RagError(Exception):
    """Base class for all knowledge-base errors."""


class RagNotFoundError(RagError):
    """Base class: something the caller asked for does not exist (HTTP 404)."""


class DocumentNotFoundError(RagNotFoundError):
    pass


class EmptyDocumentError(RagError):
    """The document has no text that could be indexed."""


class EmbeddingError(RagError):
    """The embedding model could not be loaded or failed (HTTP 503)."""


class VectorStoreError(RagError):
    """The vector database could not be opened or failed (HTTP 503)."""
