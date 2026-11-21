"""Step 3 of the pipeline: tidy raw extracted text before sending it to the LLM.

Cleaner text means fewer tokens (cheaper, faster) and less noise for the model.
"""

import re

# Control characters that are never useful (everything below space except tab and newline).
_CONTROL_CHARS = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]")


def clean_text(text: str) -> str:
    # Make every line ending a plain "\n"
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    # Non-breaking spaces (common in Word/PDF) become normal spaces
    text = text.replace("\u00a0", " ")
    # Remove invisible control characters (PDF extraction sometimes leaves \x00 etc.)
    text = _CONTROL_CHARS.sub("", text)
    # Collapse runs of spaces/tabs into one space
    text = re.sub(r"[ \t]+", " ", text)
    # Remove spaces hugging newlines
    text = re.sub(r" ?\n ?", "\n", text)
    # Allow at most one blank line in a row
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()
