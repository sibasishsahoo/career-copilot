import pytest

from app.config import Settings

ENV_NAMES = [
    "LLM_PROVIDER",
    "GEMINI_API_KEY",
    "GEMINI_MODEL",
    "ANTHROPIC_API_KEY",
    "OPENAI_API_KEY",
]


@pytest.fixture(autouse=True)
def clean_env(monkeypatch):
    """Remove real env vars so these tests behave the same on every machine."""
    for name in ENV_NAMES:
        monkeypatch.delenv(name, raising=False)


def test_defaults():
    s = Settings(_env_file=None)
    assert s.llm_provider == "gemini"
    assert s.gemini_api_key is None
    assert s.llm_is_configured is False


def test_reads_values_from_environment(monkeypatch):
    monkeypatch.setenv("GEMINI_API_KEY", "fake-key-123")
    monkeypatch.setenv("GEMINI_MODEL", "some-other-model")
    s = Settings(_env_file=None)
    assert s.gemini_api_key == "fake-key-123"
    assert s.gemini_model == "some-other-model"
    assert s.llm_is_configured is True


def test_blank_key_counts_as_not_configured(monkeypatch):
    monkeypatch.setenv("GEMINI_API_KEY", "   ")
    assert Settings(_env_file=None).llm_is_configured is False


def test_configured_checks_the_selected_provider_only(monkeypatch):
    monkeypatch.setenv("GEMINI_API_KEY", "fake-key-123")
    monkeypatch.setenv("LLM_PROVIDER", "openai")  # but no OpenAI key
    assert Settings(_env_file=None).llm_is_configured is False
