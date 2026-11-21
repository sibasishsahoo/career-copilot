"""Reads a simple notes file: several notes separated by a line containing only ---.

    # Faster deployments
    Situation: ...

    ---

    # Mentoring interns
    Situation: ...

The first line starting with "#" becomes the title.
"""


def parse_notes(text: str) -> list[tuple[str, str]]:
    notes: list[tuple[str, str]] = []
    for block in text.replace("\r\n", "\n").split("\n---\n"):
        lines = block.strip().split("\n")
        title = ""
        body_lines = lines
        if lines and lines[0].lstrip().startswith("#"):
            title = lines[0].lstrip().lstrip("#").strip()
            body_lines = lines[1:]
        body = "\n".join(body_lines).strip()
        if not body:
            continue
        notes.append((title or f"Untitled note {len(notes) + 1}", body))
    return notes
