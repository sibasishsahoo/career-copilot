"""Pydantic schemas for the knowledge base endpoints."""

from pydantic import BaseModel, ConfigDict, Field

MAX_DOCUMENT_CHARS = 50_000
MAX_QUESTION_CHARS = 500


# ---------- what the LLM must return when answering ----------

class RagAnswer(BaseModel):
    answer: str = Field(min_length=1)
    sources_used: list[int]  # the model must include this (use [] if it used none)


# ---------- requests ----------

class DocumentCreate(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")

    title: str = Field(min_length=1, max_length=200)
    text: str = Field(min_length=1, max_length=MAX_DOCUMENT_CHARS)


class SearchRequest(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")

    query: str = Field(min_length=1, max_length=MAX_QUESTION_CHARS)
    k: int = Field(default=4, ge=1, le=20)


class AskRequest(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")

    question: str = Field(min_length=1, max_length=MAX_QUESTION_CHARS)
    k: int = Field(default=4, ge=1, le=10)


# ---------- responses ----------

class DocumentSummary(BaseModel):
    id: str
    title: str
    chunk_count: int
    char_count: int
    created_at: str


class ChunkRead(BaseModel):
    index: int
    text: str


class DocumentDetail(DocumentSummary):
    chunks: list[ChunkRead]


class SearchResult(BaseModel):
    rank: int  # 1 = best match
    score: float  # cosine similarity
    doc_id: str
    title: str
    chunk_index: int
    text: str


class SearchResponse(BaseModel):
    query: str
    results: list[SearchResult]


class AskResponse(BaseModel):
    question: str
    answer: str
    grounded: bool  # True only if the answer cites at least one real source
    sources_used: list[int]  # numbers that refer to `sources` below
    sources: list[SearchResult]  # the retrieved chunks, numbered by `rank`
    used_llm: bool  # False when nothing relevant was found, so no LLM call was made
