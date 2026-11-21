"""Step 5 of RAG ("generation"): ask the LLM to answer from the retrieved chunks.

Three layers again, like resumes and jobs:
    answerer.py       WHAT to ask (the grounded prompt + the RagAnswer schema)
    structured.py     HOW to get reliable JSON (extract, validate, retry) - reused unchanged
    LLMClient         WHO answers (Gemini / Anthropic / OpenAI)
"""

from dataclasses import dataclass

from app.schemas.knowledge import RagAnswer
from app.services.llm.base import LLMClient
from app.services.llm.structured import generate_structured
from app.services.rag.citations import check_citations
from app.services.rag.models import SearchHit
from app.services.rag.prompts import ANSWER_SYSTEM_PROMPT, build_answer_prompt

MAX_RETRIES = 1


@dataclass(frozen=True)
class Answer:
    text: str
    sources_used: list[int]
    grounded: bool


def answer_question(llm: LLMClient, question: str, hits: list[SearchHit]) -> Answer:
    prompt = build_answer_prompt(question, [(hit.chunk.title, hit.chunk.text) for hit in hits])
    result = generate_structured(
        llm=llm,
        prompt=prompt,
        schema=RagAnswer,
        system_prompt=ANSWER_SYSTEM_PROMPT,
        max_retries=MAX_RETRIES,
    )
    used, grounded = check_citations(result.answer, result.sources_used, len(hits))
    return Answer(text=result.answer.strip(), sources_used=used, grounded=grounded)
