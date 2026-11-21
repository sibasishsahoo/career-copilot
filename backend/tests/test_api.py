from app.api.deps import get_llm
from app.main import app
from app.services.llm.base import LLMConfigError, LLMProviderError, LLMRateLimitError
from tests.fakes import FakeLLM


def use_llm(llm):
    """Make the /llm/test route use `llm` instead of a real provider."""
    app.dependency_overrides[get_llm] = lambda: llm


def raise_error(exc):
    def _raiser():
        raise exc

    app.dependency_overrides[get_llm] = _raiser


# ---------- /health ----------

def test_health_ok(client):
    response = client.get("/health")
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ok"
    assert body["llm_provider"] == "gemini"
    assert body["llm_configured"] is True


def test_health_never_leaks_the_api_key(client):
    assert "super-secret-fake-key" not in client.get("/health").text


# ---------- /llm/test ----------

def test_llm_test_returns_reply(client):
    fake = FakeLLM(reply="Hi there!")
    use_llm(fake)
    response = client.post("/llm/test", json={"prompt": "Say hi"})
    assert response.status_code == 200
    assert response.json() == {"provider": "fake", "model": "fake-model", "reply": "Hi there!"}
    assert fake.last_prompt == "Say hi"


def test_empty_prompt_is_rejected(client):
    use_llm(FakeLLM())
    assert client.post("/llm/test", json={"prompt": ""}).status_code == 422


def test_missing_prompt_is_rejected(client):
    use_llm(FakeLLM())
    assert client.post("/llm/test", json={}).status_code == 422


def test_too_long_prompt_is_rejected(client):
    use_llm(FakeLLM())
    assert client.post("/llm/test", json={"prompt": "x" * 2001}).status_code == 422


# ---------- error mapping ----------

def test_config_error_becomes_503(client):
    raise_error(LLMConfigError("GEMINI_API_KEY is not set"))
    response = client.post("/llm/test", json={"prompt": "hi"})
    assert response.status_code == 503
    assert "GEMINI_API_KEY" in response.json()["detail"]


def test_rate_limit_becomes_429(client):
    raise_error(LLMRateLimitError("slow down"))
    assert client.post("/llm/test", json={"prompt": "hi"}).status_code == 429


def test_provider_error_becomes_502(client):
    raise_error(LLMProviderError("upstream failed"))
    assert client.post("/llm/test", json={"prompt": "hi"}).status_code == 502
