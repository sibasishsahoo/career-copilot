"""A fake LLM for tests: no network, no API key, instant, free."""

from app.services.llm.base import LLMClient


class FakeLLM(LLMClient):
    provider_name = "fake"

    def __init__(self, reply: str = "Hello from the fake LLM"):
        super().__init__(model="fake-model")
        self.reply = reply
        self.last_prompt: str | None = None

    def generate(self, prompt: str, system_prompt: str | None = None) -> str:
        self.last_prompt = prompt
        return self.reply


class ScriptedLLM(LLMClient):
    """Returns pre-written replies one by one, and records every prompt it receives.

    A reply that is an Exception instance is RAISED instead of returned, which lets us
    simulate provider failures. This is how we test retry logic without a real model.
    """

    provider_name = "scripted"

    def __init__(self, replies: list):
        super().__init__(model="scripted-model")
        self.replies = list(replies)
        self.prompts: list[str] = []
        self.system_prompts: list[str | None] = []

    def generate(self, prompt: str, system_prompt: str | None = None) -> str:
        self.prompts.append(prompt)
        self.system_prompts.append(system_prompt)
        if not self.replies:
            raise AssertionError("ScriptedLLM was called more times than expected")
        reply = self.replies.pop(0)
        if isinstance(reply, Exception):
            raise reply
        return reply
