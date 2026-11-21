"""Anthropic provider (OPTIONAL - not needed for Phase 1).

Install with: pip install -r requirements-optional.txt
Written for later use; it has not been run against the real API yet.
"""

from app.services.llm.base import (
    LLMClient,
    LLMConfigError,
    LLMProviderError,
    LLMRateLimitError,
)


class AnthropicClient(LLMClient):
    provider_name = "anthropic"

    def __init__(self, api_key: str | None, model: str):
        super().__init__(model)
        if not api_key or not api_key.strip():
            raise LLMConfigError("ANTHROPIC_API_KEY is not set in backend/.env.")
        try:
            import anthropic
        except ImportError as exc:
            raise LLMConfigError(
                "The 'anthropic' package is not installed. "
                "Run: pip install -r requirements-optional.txt"
            ) from exc
        self._anthropic = anthropic
        self._client = anthropic.Anthropic(api_key=api_key.strip())

    def generate(self, prompt: str, system_prompt: str | None = None) -> str:
        kwargs = {
            "model": self.model,
            "max_tokens": 1024,
            "messages": [{"role": "user", "content": prompt}],
        }
        if system_prompt:
            kwargs["system"] = system_prompt

        try:
            response = self._client.messages.create(**kwargs)
        except self._anthropic.RateLimitError as exc:
            raise LLMRateLimitError("Anthropic rate limit reached. Try again shortly.") from exc
        except self._anthropic.APIError as exc:
            raise LLMProviderError(f"Anthropic API error: {exc}") from exc

        text = "".join(
            block.text for block in response.content if getattr(block, "type", None) == "text"
        )
        if not text:
            raise LLMProviderError("Anthropic returned an empty response.")
        return text
