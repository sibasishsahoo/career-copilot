from fastapi import APIRouter, Depends

from app.api.deps import get_llm
from app.schemas.llm import LLMTestRequest, LLMTestResponse
from app.services.llm.base import LLMClient

router = APIRouter(prefix="/llm", tags=["llm"])


# This is a plain `def`, not `async def`, on purpose. The LLM SDK call blocks
# while waiting for the network. FastAPI runs plain `def` routes in a worker
# thread, so one slow LLM call does not freeze the whole server.
@router.post("/test", response_model=LLMTestResponse)
def test_llm(body: LLMTestRequest, llm: LLMClient = Depends(get_llm)) -> LLMTestResponse:
    reply = llm.generate(body.prompt)
    return LLMTestResponse(provider=llm.provider_name, model=llm.model, reply=reply)
