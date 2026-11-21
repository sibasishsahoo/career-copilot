"""Smoke test against the REAL configured provider.

Run from the backend/ folder:   python -m scripts.check_llm
"""

import sys

from app.config import get_settings
from app.services.llm.base import LLMError
from app.services.llm.factory import get_llm_client


def main() -> int:
    settings = get_settings()
    print(f"Provider: {settings.llm_provider}")
    try:
        client = get_llm_client(settings)
        print(f"Model:    {client.model}")
        reply = client.generate("Reply with exactly one word: pong")
    except LLMError as exc:
        print(f"FAILED:   {exc}")
        return 1
    print(f"Reply:    {reply}")
    print("OK - the real LLM integration works on your machine.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
