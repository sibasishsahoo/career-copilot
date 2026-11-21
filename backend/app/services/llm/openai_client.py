"""OpenAI provider (OPTIONAL - not needed for Phase 1).

Install with: pip install -r requirements-optional.txt
Written for later use; it has not been run against the real API yet.
"""

from app.services.llm.base import (
    LLMClient,
    LLMConfigError,
    LLMProviderError,
    LLMRateLimitError,
)


class OpenAIClient(LLMClient):
    provider_name = "openai"

    def __init__(self, api_key: str | None, model: str):
        super().__init__(model)
        if not api_key or not api_key.strip():
            raise LLMConfigError("OPENAI_API_KEY is not set in backend/.env.")
        try:
            import openai
        except ImportError as exc:
            raise LLMConfigError(
                "The 'openai' package is not installed. "
                "Run: pip install -r requirements-optional.txt"
            ) from exc
        self._openai = openai
        self._client = openai.OpenAI(api_key=api_key.strip())

    def generate(self, prompt: str, system_prompt: str | None = None) -> str:
        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})

        try:
            response = self._client.chat.completions.create(model=self.model, messages=messages)
        except self._openai.RateLimitError as exc:
            raise LLMRateLimitError("OpenAI rate limit reached. Try again shortly.") from exc
        except self._openai.APIError as exc:
            raise LLMProviderError(f"OpenAI API error: {exc}") from exc

        text = response.choices[0].message.content
        if not text:
            raise LLMProviderError("OpenAI returned an empty response.")
        return text
