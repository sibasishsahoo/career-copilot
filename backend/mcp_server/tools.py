"""The logic of every tool, as plain Python functions that take an ApiClient.

Nothing here knows about MCP. server.py only REGISTERS these functions with the SDK, so all the
behaviour (validation, mapping the backend's answers into compact results) can be tested without
the SDK installed.

The three tools deliberately mirror the agent's tools from Phase 7 (same names, same argument limits,
same result shapes), so an AI app using MCP sees exactly what your own agent sees.
"""

import json
from typing import Any

from mcp_server.api_client import ApiClient, BackendError

# Same limits as the agent's tools (backend/app/services/agent/*_tools.py); a parity test checks it.
STATUSES = ("wishlist", "applied", "interviewing", "offer", "rejected", "withdrawn")
LIMIT_DEFAULT, LIMIT_MIN, LIMIT_MAX = 10, 1, 25
K_DEFAULT, K_MIN, K_MAX = 3, 1, 5
SEARCH_MAX_CHARS = 100
QUERY_MAX_CHARS = 500
FOCUS_MAX_CHARS = 300
NOTES_EXCERPT_CHARS = 800
JOB_EXCERPT_CHARS = 600


class ToolInputError(Exception):
    """The caller (the AI app) passed an argument that is not allowed. Written for the model to read."""


# ---------------------------------------------------------------------------------------------
# Argument checks
# ---------------------------------------------------------------------------------------------

def _int_argument(name: str, value: Any, minimum: int, maximum: int | None = None) -> int:
    if isinstance(value, bool):
        raise ToolInputError(f"'{name}' must be an integer.")
    if isinstance(value, float) and value.is_integer():
        value = int(value)
    if isinstance(value, str) and value.strip().lstrip("-").isdigit():
        value = int(value.strip())
    if not isinstance(value, int):
        raise ToolInputError(f"'{name}' must be an integer.")
    if value < minimum:
        raise ToolInputError(f"'{name}' must be at least {minimum}.")
    if maximum is not None and value > maximum:
        raise ToolInputError(f"'{name}' must be at most {maximum}.")
    return value


def _status_argument(value: Any) -> str | None:
    if value is None or (isinstance(value, str) and not value.strip()):
        return None
    if isinstance(value, str):
        for status in STATUSES:
            if status == value.strip().lower():
                return status
    raise ToolInputError(f"'status' must be one of: {', '.join(STATUSES)}.")


def _text_argument(name: str, value: Any, maximum: int, required: bool) -> str | None:
    if value is None:
        if required:
            raise ToolInputError(f"'{name}' is required.")
        return None
    if not isinstance(value, str):
        raise ToolInputError(f"'{name}' must be a string.")
    text = value.strip()
    if not text:
        if required:
            raise ToolInputError(f"'{name}' must not be empty.")
        return None
    if len(text) > maximum:
        raise ToolInputError(f"'{name}' must be at most {maximum} characters.")
    return text


def _excerpt(text: str | None, limit: int) -> str | None:
    if text is None:
        return None
    return text if len(text) <= limit else text[:limit] + "..."


def _expect(value: Any, kind: type, what: str) -> Any:
    if not isinstance(value, kind):
        raise BackendError(f"The backend returned an unexpected response for {what}.")
    return value


# ---------------------------------------------------------------------------------------------
# The tools
# ---------------------------------------------------------------------------------------------

def _summary(application: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": application.get("id"),
        "company": application.get("company"),
        "job_title": application.get("job_title"),
        "status": application.get("status"),
        "location": application.get("location"),
        "applied_date": application.get("applied_date"),
        "updated_at": application.get("updated_at"),
    }


def list_applications(
    api: ApiClient,
    status: Any = None,
    search: Any = None,
    limit: Any = LIMIT_DEFAULT,
) -> dict[str, Any]:
    params = {
        "status": _status_argument(status),
        "search": _text_argument("search", search, SEARCH_MAX_CHARS, required=False),
        "limit": _int_argument("limit", limit, LIMIT_MIN, LIMIT_MAX),
    }
    applications = _expect(api.get("/applications", params), list, "the application list")
    entries = [_summary(item) for item in applications if isinstance(item, dict)]
    return {"count": len(entries), "applications": entries}


def get_application(api: ApiClient, application_id: Any) -> dict[str, Any]:
    number = _int_argument("application_id", application_id, 1)
    detail = _expect(api.get(f"/applications/{number}"), dict, f"application {number}")

    snapshot = detail.get("match_snapshot")
    saved_match = None
    if isinstance(snapshot, dict):
        saved_match = {
            "score": snapshot.get("score"),
            "matched_skills": snapshot.get("matched_skills"),
            "missing_skills": snapshot.get("missing_skills"),
            "job_description_excerpt": _excerpt(snapshot.get("job_description"), JOB_EXCERPT_CHARS),
        }

    history = detail.get("status_history")
    return {
        **_summary(detail),
        "job_url": detail.get("job_url"),
        "notes": _excerpt(detail.get("notes"), NOTES_EXCERPT_CHARS),
        "status_history": [
            {"from": change.get("from_status"), "to": change.get("to_status"),
             "note": change.get("note"), "at": change.get("changed_at")}
            for change in (history if isinstance(history, list) else [])
            if isinstance(change, dict)
        ],
        "saved_match": saved_match,
    }


def search_knowledge(api: ApiClient, query: Any, k: Any = K_DEFAULT, min_score: Any = 0.0) -> dict[str, Any]:
    text = _text_argument("query", query, QUERY_MAX_CHARS, required=True)
    count = _int_argument("k", k, K_MIN, K_MAX)
    if isinstance(min_score, bool) or not isinstance(min_score, (int, float)) or not 0.0 <= min_score <= 1.0:
        raise ToolInputError("'min_score' must be a number between 0 and 1.")

    response = _expect(api.post("/knowledge/search", {"query": text, "k": count}), dict, "the notes search")
    results = _expect(response.get("results"), list, "the notes search")
    matches = [
        {"note": item.get("title"), "score": item.get("score"), "text": item.get("text")}
        for item in results
        if isinstance(item, dict) and isinstance(item.get("score"), (int, float)) and item["score"] >= min_score
    ]
    if not matches:
        return {"count": 0, "matches": [], "message": "No notes matched this query."}
    return {"count": len(matches), "matches": matches}


def render(result: Any) -> str:
    """Compact JSON text, which is what the AI model reads."""
    return json.dumps(result, ensure_ascii=False, separators=(",", ":"))


# ---------------------------------------------------------------------------------------------
# The prompt template
# ---------------------------------------------------------------------------------------------

def build_interview_prompt(application_id: Any, focus: Any = "") -> str:
    number = _int_argument("application_id", application_id, 1)
    focus_text = _text_argument("focus", focus, FOCUS_MAX_CHARS, required=False)
    lines = [
        "Help me prepare for a job interview. Work only from my own data, using the career-copilot tools. "
        "Never invent anything about me.",
        "",
        "Steps:",
        f"1. Call get_application with application_id {number} to see the role, the company, my status "
        "history, and my saved job match (the skills I matched and the ones I am missing).",
        "2. Call search_knowledge several times to find my own stories and achievements that fit this job: "
        "once for the role itself and once for each missing or required skill.",
        "3. Then write:",
        "   - the 5 questions I am most likely to be asked for this role;",
        "   - for each one, which of my notes (by title) I could use as a STAR answer, with a two-sentence outline;",
        "   - the skills I am missing, with an honest way to talk about each (never claim experience I do not have);",
        "   - 3 good questions for me to ask the interviewer.",
        "",
        "If a tool returns nothing useful, say so instead of guessing.",
    ]
    if focus_text:
        lines += ["", f"Pay special attention to: {focus_text}"]
    return "\n".join(lines)
