"""Provider-independent structured output: prompt -> JSON -> validated Pydantic object.

This sits ABOVE the provider clients and only uses the `LLMClient` interface
(`llm.generate(prompt, system_prompt)`). It knows nothing about Gemini, Anthropic
or OpenAI, and nothing about resumes - so Phase 3 (job descriptions) reuses it as is.

The loop, in plain words:

    1. Ask the model.
    2. Try to extract JSON from its reply.           (can fail: JSONExtractionError)
    3. Validate the JSON against our Pydantic model. (can fail: ValidationError)
    4. If it worked, return the validated object.
    5. If it failed, tell the model exactly what was wrong and ask again.
    6. After max_retries extra attempts, give up with LLMOutputError.

Errors raised by the provider itself (bad API key, rate limit, network) are NOT
retried here - they pass straight through, because asking again won't fix them.
"""

import logging
from typing import TypeVar

from pydantic import BaseModel, ValidationError

from app.services.llm.base import LLMClient, LLMOutputError
from app.services.llm.json_utils import JSONExtractionError, extract_json_object

logger = logging.getLogger(__name__)

T = TypeVar("T", bound=BaseModel)

# How much of the model's previous bad reply we echo back in the retry prompt.
MAX_ECHO_CHARS = 1500


def format_validation_error(exc: ValidationError, max_items: int = 10) -> str:
    """Turn a Pydantic ValidationError into a short, readable list of problems.

    Example result:
        "full_name: Field required; experience.0.company: Field required"
    """
    errors = exc.errors()
    problems = []
    for error in errors[:max_items]:
        # `loc` is the path to the bad field, e.g. ("experience", 0, "company")
        location = ".".join(str(part) for part in error["loc"]) or "(whole object)"
        problems.append(f"{location}: {error['msg']}")
    if len(errors) > max_items:
        problems.append(f"...and {len(errors) - max_items} more problems")
    return "; ".join(problems)


def build_retry_prompt(original_prompt: str, previous_reply: str, problem: str) -> str:
    """Original request + what went wrong, so the model can correct itself."""
    return (
        f"{original_prompt}\n\n"
        "---\n"
        "Your previous reply could not be used.\n"
        f"Problem: {problem}\n\n"
        f"Your previous reply was:\n{previous_reply[:MAX_ECHO_CHARS]}\n\n"
        "Reply again with ONE corrected JSON object only, following the format exactly."
    )


def generate_structured(
    llm: LLMClient,
    prompt: str,
    schema: type[T],
    system_prompt: str | None = None,
    max_retries: int = 1,
) -> T:
    """Ask the LLM for JSON and return it validated as `schema`.

    max_retries=1 means: at most 2 calls in total (1 first try + 1 retry).
    """
    current_prompt = prompt
    last_problem = ""
    total_attempts = max_retries + 1

    for attempt in range(1, total_attempts + 1):
        reply = llm.generate(current_prompt, system_prompt)

        try:
            data = extract_json_object(reply)  # step 2
            return schema.model_validate(data)  # step 3
        except JSONExtractionError as exc:
            last_problem = str(exc)
        except ValidationError as exc:
            last_problem = format_validation_error(exc)

        logger.warning(
            "Structured output attempt %d/%d failed: %s", attempt, total_attempts, last_problem
        )
        current_prompt = build_retry_prompt(prompt, reply, last_problem)  # step 5

    raise LLMOutputError(
        f"The AI model did not return valid structured data after {total_attempts} attempts. "
        f"Last problem: {last_problem}"
    )
