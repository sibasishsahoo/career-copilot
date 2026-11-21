"""Step 2 of RAG: turn text into vectors ("embeddings").

An embedding model reads a text and returns a list of numbers. Texts about similar things get
similar lists. Everything else in RAG (search, ranking) is just math on those lists.

Our code only depends on the tiny `Embedder` interface, exactly like the LLM provider interface in
Phase 1, so the model can be swapped without touching the rest of the pipeline.
"""

import hashlib
import re
from abc import ABC, abstractmethod

from app.services.rag.errors import EmbeddingError
from app.services.rag.similarity import normalize


class Embedder(ABC):
    name: str = "embedder"  # used to keep vectors from different models in separate collections
    # Similarity scores are not comparable between models, so each model suggests its own cut-off:
    # chunks scoring below it are not shown to the LLM. (RAG_MIN_SCORE in .env overrides it.)
    default_min_score: float = 0.25

    @abstractmethod
    def embed(self, texts: list[str]) -> list[list[float]]:
        """Return one vector per text, in the same order."""


# ----------------------------------------------------------------------------------------------
# 1. The real thing: a small neural network that runs on your own machine.
# ----------------------------------------------------------------------------------------------

class LocalEmbedder(Embedder):
    """all-MiniLM-L6-v2 (384 numbers per text), run locally through the ONNX runtime that ships with
    chromadb. No API key and no PyTorch. The first use downloads the model (about 80 MB)."""

    name = "local-minilm"

    def __init__(self) -> None:
        self._function = None

    def _load(self):
        if self._function is None:
            try:
                from chromadb.utils.embedding_functions import DefaultEmbeddingFunction
            except ImportError as exc:
                raise EmbeddingError(
                    "The 'chromadb' package is not installed. Run: pip install -r requirements.txt"
                ) from exc
            try:
                self._function = DefaultEmbeddingFunction()
            except Exception as exc:
                raise EmbeddingError(f"Could not create the local embedding model: {exc}") from exc
        return self._function

    def embed(self, texts: list[str]) -> list[list[float]]:
        if not texts:
            return []
        function = self._load()
        try:
            vectors = function(texts)  # the first call downloads the model if it is missing
        except Exception as exc:
            raise EmbeddingError(
                "The local embedding model failed. The first run needs internet to download it "
                f"(about 80 MB). Details: {exc}"
            ) from exc
        return [[float(number) for number in vector] for vector in vectors]


# ----------------------------------------------------------------------------------------------
# 2. A tiny stand-in that needs no download - and shows what an embedding "is".
# ----------------------------------------------------------------------------------------------

_WORD = re.compile(r"[a-z0-9]+(?:'[a-z]+)?")
_STOPWORDS = frozenset(
    "a an and are as at be by for from i in is it its me my of on or that the this to was were with".split()
)


class HashingEmbedder(Embedder):
    """The "hashing trick": each word is hashed to one of `dimensions` positions and counted.

    This is NOT semantic. "car" and "automobile" look unrelated to it, and so do "deploy" and
    "deployment" (there is no stemming): only IDENTICAL WORDS make two texts similar, so its
    rankings are often poor. It exists for tests, offline demos, and to show how little an embedding
    needs to be - a list of numbers where similar texts give similar lists - and, by contrast, why
    a real model (LocalEmbedder) is worth having.
    """

    default_min_score = 0.05  # word-overlap scores are small; a real model's cut-off would hide everything

    def __init__(self, dimensions: int = 512) -> None:
        if dimensions < 8:
            raise ValueError("dimensions must be at least 8.")
        self.dimensions = dimensions
        self.name = f"hashing-{dimensions}"

    def embed(self, texts: list[str]) -> list[list[float]]:
        return [self._embed_one(text) for text in texts]

    def _embed_one(self, text: str) -> list[float]:
        vector = [0.0] * self.dimensions
        for word in _WORD.findall(text.lower()):
            if word in _STOPWORDS:
                continue
            # md5 (not Python's hash()) so the result is identical on every run and machine
            digest = hashlib.md5(word.encode("utf-8")).digest()
            vector[int.from_bytes(digest[:4], "big") % self.dimensions] += 1.0
        return normalize(vector)
