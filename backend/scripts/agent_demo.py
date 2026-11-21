"""Ask the agent a question using your REAL data and the real LLM, and watch it work.

Run from the backend/ folder:

    python -m scripts.agent_demo "Which of my applications is furthest along?"
    python -m scripts.agent_demo "Which of my stories shows leadership?"
    python -m scripts.agent_demo "What happened with my Acme application, and what story of mine fits it?"

The agent can only READ your tracker and your notes. Each step is one LLM call, so one question uses
about 2 to 4 calls: on the Gemini free tier wait a minute between questions.
"""

import argparse
import sys

from app.api.deps import get_knowledge_provider
from app.config import get_settings
from app.db.session import get_session_factory, init_db
from app.services.agent.builtin_tools import build_registry
from app.services.agent.decider import LLMDecider
from app.services.agent.loop import run_agent
from app.services.llm.base import LLMError
from app.services.llm.factory import get_llm_client


def shorten(text: str, limit: int = 300) -> str:
    return text if len(text) <= limit else text[:limit] + "..."


def main() -> int:
    parser = argparse.ArgumentParser(description="Ask the career agent a question.")
    parser.add_argument("question")
    args = parser.parse_args()

    settings = get_settings()
    init_db()  # make sure the tracker tables exist, even if the server never ran
    try:
        llm = get_llm_client(settings)
        with get_session_factory()() as db:
            registry = build_registry(db, get_knowledge_provider(settings), settings.rag_min_score)
            result = run_agent(LLMDecider(llm), registry, args.question, settings.agent_max_steps)
    except LLMError as exc:
        print(f"FAILED: {exc}")
        return 1

    for step in result.steps:
        print(f"\nStep {step.number}  {'ok' if step.ok else 'ERROR'}")
        if step.thought:
            print(f"  thought:     {step.thought}")
        print(f"  call:        {step.tool} {step.arguments}")
        print(f"  observation: {shorten(step.observation)}")
    print(f"\nAnswer ({result.stopped_reason}):\n{result.answer}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
