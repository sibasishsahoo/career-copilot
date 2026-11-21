"""Gemini provider, using Google's official `google-genai` SDK."""

from app.services.llm.base import (
    LLMClient,
    LLMConfigError,
    LLMProviderError,
    LLMRateLimitError,
)


class GeminiClient(LLMClient):
    provider_name = "gemini"

    def __init__(self, api_key: str | None, model: str):
        super().__init__(model)

        # Check the key BEFORE importing the SDK so the error is clear and fast.
        if not api_key or not api_key.strip():
            raise LLMConfigError(
                "GEMINI_API_KEY is not set. Create backend/.env from .env.example "
                "and add your key (get one at https://aistudio.google.com/apikey)."
            )

        try:
            from google import genai
        except ImportError as exc:
            raise LLMConfigError(
                "The 'google-genai' package is not installed. "
                "Run: pip install -r requirements.txt"
            ) from exc

        # We pass the key explicitly. pydantic-settings reads .env into our
        # Settings object but does NOT put it into os.environ, so the SDK
        # would not find it on its own.
        self._client = genai.Client(api_key=api_key.strip())

    def generate(self, prompt: str, system_prompt: str | None = None) -> str:
        from google.genai import errors, types

        config = None
        if system_prompt:
            config = types.GenerateContentConfig(system_instruction=system_prompt)

        try:
            response = self._client.models.generate_content(
                model=self.model,
                contents=prompt,
                config=config,
            )
        except errors.APIError as exc:
            code = getattr(exc, "code", None)
            message = getattr(exc, "message", str(exc))
            if code == 429:
                raise LLMRateLimitError(
                    "Gemini rate limit reached. The free tier allows only a few "
                    "requests per minute - wait a minute and try again."
                ) from exc
            raise LLMProviderError(f"Gemini API error (code {code}): {message}") from exc
        except Exception as exc:  # network down, DNS failure, etc.
            raise LLMProviderError(f"Could not reach the Gemini API: {exc}") from exc

        # response.text can be empty/None, e.g. when a safety filter blocks the answer.
        text = response.text
        if not text:
            raise LLMProviderError(
                "Gemini returned an empty response (it may have been blocked by a safety filter)."
            )
        return text
