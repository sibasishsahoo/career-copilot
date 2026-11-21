"""Step 1 of RAG: split a document into chunks.

Why chunk at all?
  * An embedding summarizes ONE piece of text. A whole 5-page document squeezed into one vector
    becomes blurry; a paragraph-sized chunk keeps a sharp meaning that a question can match.
  * We send only the best few chunks to the LLM, which keeps the prompt small, cheap and focused.

How we split (a "recursive" splitter, written from scratch):
  1. Try to cut at the biggest natural boundary: blank lines between paragraphs.
  2. A paragraph still too long? Cut at line breaks, then at sentence ends, then between words.
  3. Pack the small pieces back together (greedily) until a chunk is about `chunk_size` characters.
  4. Overlap: each chunk starts with the last few words of the chunk before it, so a sentence
     that sits on a boundary is still fully visible in at least one chunk.
"""

import re

_CONTROL_CHARS = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]")


def normalize_text(text: str) -> str:
    """Tidy whitespace so chunks do not contain noise."""
    text = text.replace("\r\n", "\n").replace("\r", "\n").replace("\u00a0", " ")
    text = _CONTROL_CHARS.sub("", text)
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r" ?\n ?", "\n", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def _split_paragraphs(text: str) -> list[str]:
    return re.split(r"\n\s*\n", text)


def _split_lines(text: str) -> list[str]:
    return text.split("\n")


def _split_sentences(text: str) -> list[str]:
    return re.split(r"(?<=[.!?])\s+", text)


def _split_words(text: str) -> list[str]:
    return text.split()


# From the biggest boundary to the smallest, each with the text used to glue pieces back together.
_LEVELS = (
    (_split_paragraphs, "\n\n"),
    (_split_lines, "\n"),
    (_split_sentences, " "),
    (_split_words, " "),
)


def _split_to_size(text: str, size: int, level: int = 0) -> list[str]:
    """Break `text` into pieces of at most `size` characters, cutting at the biggest boundary possible."""
    if len(text) <= size:
        return [text]
    if level >= len(_LEVELS):
        # No natural boundary left (e.g. one gigantic "word"): cut blindly every `size` characters.
        return [text[i : i + size] for i in range(0, len(text), size)]

    split, glue = _LEVELS[level]
    parts = [part.strip() for part in split(text) if part.strip()]
    if len(parts) <= 1:
        return _split_to_size(text, size, level + 1)  # this boundary does not occur here

    pieces: list[str] = []
    current = ""
    for part in parts:
        if len(part) > size:
            # Too big even alone: finish the current piece, then split this part more finely.
            if current:
                pieces.append(current)
                current = ""
            pieces.extend(_split_to_size(part, size, level + 1))
            continue

        candidate = part if not current else current + glue + part
        if len(candidate) <= size:
            current = candidate
        else:
            pieces.append(current)
            current = part
    if current:
        pieces.append(current)
    return pieces


def _overlap_prefix(previous_piece: str, overlap: int) -> str:
    """The last ~`overlap` characters of the previous piece, without starting in the middle of a word."""
    if overlap <= 0 or not previous_piece:
        return ""
    tail = previous_piece[-overlap:]
    starts_mid_word = len(previous_piece) > overlap and not previous_piece[-overlap - 1].isspace()
    if starts_mid_word:
        parts = tail.split(None, 1)  # drop the first, possibly cut-off, word
        tail = parts[1] if len(parts) == 2 else ""
    return tail.strip()


def chunk_text(text: str, chunk_size: int = 800, overlap: int = 150) -> list[str]:
    """Split `text` into chunks.

    `chunk_size` is the target size of the NEW text in each chunk; the overlap is added on top,
    so a chunk is at most chunk_size + overlap + 1 characters long.
    """
    if chunk_size < 1:
        raise ValueError("chunk_size must be at least 1.")
    if overlap < 0 or overlap >= chunk_size:
        raise ValueError("overlap must be at least 0 and smaller than chunk_size.")

    normalized = normalize_text(text)
    if not normalized:
        return []

    pieces = _split_to_size(normalized, chunk_size)
    chunks = [pieces[0]]
    for previous, piece in zip(pieces, pieces[1:]):
        prefix = _overlap_prefix(previous, overlap)
        chunks.append(f"{prefix} {piece}" if prefix else piece)
    return chunks
