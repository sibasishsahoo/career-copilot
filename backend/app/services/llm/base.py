"""The LLM provider abstraction.

The rest of the app only knows about `LLMClient.generate(prompt)`. It does not
know or care whether Gemini, Anthropic or OpenAI answers. To support a new
provider you write one new class with a `generate` method - nothing else changes.
"""

from abc import ABC, abstractmethod


class LLMError(Exception):
    """Base class for every LLM-related error."""


class LLMConfigError(LLMError):
    """Our setup is wrong: missing API key, unknown provider, package not installed."""


class LLMProviderError(LLMError):
    """The provider's API call failed (bad key, network problem, server error...)."""


class LLMRateLimitError(LLMProviderError):
    """The provider says we are sending requests too fast (HTTP 429)."""


class LLMOutputError(LLMProviderError):
    """The model answered, but its output was unusable even after retries
    (not valid JSON, or JSON that does not match the expected schema)."""


class LLMClient(ABC):
    """Interface every provider must implement."""

    provider_name: str = "unknown"

    def __init__(self, model: str):
        self.model = model

    @abstractmethod
    def generate(self, prompt: str, system_prompt: str | None = None) -> str:
        """Send a prompt to the model and return the reply as plain text."""
