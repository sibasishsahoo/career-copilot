import pytest

from app.config import Settings
from app.services.llm.base import LLMConfigError
from app.services.llm.factory import get_llm_client


def make_settings(**overrides) -> Settings:
    # _env_file=None -> ignore the real .env; explicit values beat shell env vars.
    return Settings(_env_file=None, **overrides)


def test_unknown_provider_raises_clear_error():
    with pytest.raises(LLMConfigError, match="Unknown LLM_PROVIDER"):
        get_llm_client(make_settings(llm_provider="banana"))


def test_gemini_without_key_raises():
    with pytest.raises(LLMConfigError, match="GEMINI_API_KEY"):
        get_llm_client(make_settings(llm_provider="gemini", gemini_api_key=None))


def test_anthropic_without_key_raises():
    with pytest.raises(LLMConfigError, match="ANTHROPIC_API_KEY"):
        get_llm_client(make_settings(llm_provider="anthropic", anthropic_api_key=None))


def test_openai_without_key_raises():
    with pytest.raises(LLMConfigError, match="OPENAI_API_KEY"):
        get_llm_client(make_settings(llm_provider="openai", openai_api_key=None))


def test_gemini_with_key_builds_gemini_client():
    pytest.importorskip("google.genai")  # skip if the SDK is not installed
    from app.services.llm.gemini_client import GeminiClient

    settings = make_settings(llm_provider="GEMINI", gemini_api_key="fake-key")
    client = get_llm_client(settings)  # building the client makes no network call
    assert isinstance(client, GeminiClient)
    assert client.model == settings.gemini_model
