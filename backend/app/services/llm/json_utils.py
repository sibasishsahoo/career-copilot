"""Step 1 of structured output: pull a JSON object out of the model's text reply.

Even when told "reply with JSON only", models often add things around it:

    Here is the JSON you asked for:
    ```json
    {"name": "Ana"}
    ```
    Let me know if you need anything else!

This module finds the JSON object inside such a reply and parses it with the
standard library. It does NOT check that the JSON has the right fields - that
is Pydantic's job in the next step (see structured.py).
"""

import json
import re


class JSONExtractionError(Exception):
    """The reply contained no JSON object, or the JSON was malformed."""


# Matches a ```json ... ``` (or plain ``` ... ```) code fence and captures what is inside.
_FENCE_PATTERN = re.compile(r"```(?:json)?\s*(.*?)```", re.DOTALL | re.IGNORECASE)


def extract_json_object(reply: str) -> dict:
    """Return the first JSON object found in `reply` as a Python dict."""
    text = reply.strip()

    # 1. If the model wrapped its answer in a code fence, look only inside it.
    fence = _FENCE_PATTERN.search(text)
    if fence:
        text = fence.group(1).strip()

    # 2. Skip any chatter before the first "{".
    start = text.find("{")
    if start == -1:
        raise JSONExtractionError("No JSON object found in the reply (no '{' character).")

    # 3. raw_decode parses ONE JSON value starting at `start` and ignores whatever
    #    text follows it, so trailing chatter is harmless.
    try:
        data, _end = json.JSONDecoder().raw_decode(text[start:])
    except json.JSONDecodeError as exc:
        raise JSONExtractionError(
            f"The reply contains malformed JSON: {exc.msg} (line {exc.lineno}, column {exc.colno})."
        ) from exc

    return data  # always a dict, because we started parsing at a "{"
