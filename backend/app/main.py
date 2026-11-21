"""Application entry point: creates the FastAPI app and wires everything together."""

from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from app.api import agent, applications, health, interview, jobs, knowledge, llm, resumes
from app.db.session import init_db
from app.services.application_service import TrackerNotFoundError
from app.services.interview.errors import InterviewGenerationError, NoSavedMatchError
from app.services.job.errors import EmptyJobDescriptionError, NoSkillsToCompareError
from app.services.llm.base import LLMConfigError, LLMProviderError, LLMRateLimitError
from app.services.rag.errors import (
    EmbeddingError,
    EmptyDocumentError,
    RagNotFoundError,
    VectorStoreError,
)
from app.services.resume.errors import (
    FileTooLargeError,
    InvalidFileError,
    NoTextFoundError,
    UnsupportedFileTypeError,
)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Runs once at server startup (code before `yield`) and shutdown (code after it)."""
    init_db()  # create the database tables if they do not exist yet
    yield


app = FastAPI(title="AI Career Copilot API", version="0.9.0", lifespan=lifespan)

app.include_router(health.router)
app.include_router(llm.router)
app.include_router(resumes.router)
app.include_router(jobs.router)
app.include_router(applications.router)
app.include_router(knowledge.router)
app.include_router(agent.router)
app.include_router(interview.router)


# --- Turn our own exceptions into clean HTTP responses -----------------------
# Services raise plain Python exceptions; they know nothing about HTTP.
# These handlers are the single place where exception -> status code is decided.
# FastAPI picks the most specific handler (e.g. LLMRateLimitError before LLMProviderError).
# LLMOutputError (bad JSON after retries) is a subclass of LLMProviderError, so it gets 502.

def _error(status_code: int, exc: Exception) -> JSONResponse:
    return JSONResponse(status_code=status_code, content={"detail": str(exc)})


# LLM errors
@app.exception_handler(LLMConfigError)
async def handle_config_error(request: Request, exc: LLMConfigError) -> JSONResponse:
    return _error(503, exc)  # server is not set up correctly (e.g. missing API key)


@app.exception_handler(LLMRateLimitError)
async def handle_rate_limit(request: Request, exc: LLMRateLimitError) -> JSONResponse:
    return _error(429, exc)  # too many requests


@app.exception_handler(LLMProviderError)
async def handle_provider_error(request: Request, exc: LLMProviderError) -> JSONResponse:
    return _error(502, exc)  # the upstream LLM service failed or returned unusable output


# Resume errors
@app.exception_handler(UnsupportedFileTypeError)
async def handle_unsupported_type(request: Request, exc: UnsupportedFileTypeError) -> JSONResponse:
    return _error(415, exc)  # Unsupported Media Type


@app.exception_handler(FileTooLargeError)
async def handle_too_large(request: Request, exc: FileTooLargeError) -> JSONResponse:
    return _error(413, exc)  # Payload Too Large


@app.exception_handler(InvalidFileError)
async def handle_invalid_file(request: Request, exc: InvalidFileError) -> JSONResponse:
    return _error(400, exc)  # Bad Request: empty / corrupt / fake extension


@app.exception_handler(NoTextFoundError)
async def handle_no_text(request: Request, exc: NoTextFoundError) -> JSONResponse:
    return _error(422, exc)  # file is fine, but we cannot process its content


# Job errors
@app.exception_handler(EmptyJobDescriptionError)
async def handle_empty_job(request: Request, exc: EmptyJobDescriptionError) -> JSONResponse:
    return _error(422, exc)


@app.exception_handler(NoSkillsToCompareError)
async def handle_no_skills(request: Request, exc: NoSkillsToCompareError) -> JSONResponse:
    return _error(422, exc)  # the posting listed no skills, so a comparison is meaningless


# Tracker errors
@app.exception_handler(TrackerNotFoundError)
async def handle_tracker_not_found(request: Request, exc: TrackerNotFoundError) -> JSONResponse:
    return _error(404, exc)  # covers ApplicationNotFoundError and MatchSnapshotNotFoundError


# Knowledge base (RAG) errors
@app.exception_handler(RagNotFoundError)
async def handle_rag_not_found(request: Request, exc: RagNotFoundError) -> JSONResponse:
    return _error(404, exc)


@app.exception_handler(EmptyDocumentError)
async def handle_empty_document(request: Request, exc: EmptyDocumentError) -> JSONResponse:
    return _error(422, exc)


@app.exception_handler(EmbeddingError)
async def handle_embedding_error(request: Request, exc: EmbeddingError) -> JSONResponse:
    return _error(503, exc)  # the embedding model could not be loaded or failed


@app.exception_handler(VectorStoreError)
async def handle_vector_store_error(request: Request, exc: VectorStoreError) -> JSONResponse:
    return _error(503, exc)  # the vector database could not be opened or failed


# Interview preparation errors
@app.exception_handler(NoSavedMatchError)
async def handle_no_saved_match(request: Request, exc: NoSavedMatchError) -> JSONResponse:
    return _error(409, exc)  # the request is fine, but the application is not ready for it


@app.exception_handler(InterviewGenerationError)
async def handle_interview_generation(request: Request, exc: InterviewGenerationError) -> JSONResponse:
    return _error(502, exc)  # the AI returned nothing usable
