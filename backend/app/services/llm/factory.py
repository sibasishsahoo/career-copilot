"""Chooses which LLM client to build, based on LLM_PROVIDER in the settings."""

from app.config import Settings
from app.services.llm.base import LLMClient, LLMConfigError

SUPPORTED_PROVIDERS = ("gemini", "anthropic", "openai")


def get_llm_client(settings: Settings) -> LLMClient:
    provider = settings.llm_provider.strip().lower()

    # Imports are inside each branch so that, for example, the OpenAI code is
    # never loaded unless you actually select OpenAI.
    if provider == "gemini":
        from app.services.llm.gemini_client import GeminiClient

        return GeminiClient(api_key=settings.gemini_api_key, model=settings.gemini_model)

    if provider == "anthropic":
        from app.services.llm.anthropic_client import AnthropicClient

        return AnthropicClient(api_key=settings.anthropic_api_key, model=settings.anthropic_model)

    if provider == "openai":
        from app.services.llm.openai_client import OpenAIClient

        return OpenAIClient(api_key=settings.openai_api_key, model=settings.openai_model)

    raise LLMConfigError(
        f"Unknown LLM_PROVIDER '{settings.llm_provider}'. "
        f"Supported values: {', '.join(SUPPORTED_PROVIDERS)}."
    )
