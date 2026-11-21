"""A tiny HTTP client for the Career Copilot backend, using only the standard library.

Two safety properties are built in, because this client sits between an AI app and your data:
  * READ-ONLY BY CONSTRUCTION: only three request shapes are allowed (see ALLOWED_REQUESTS).
    Anything else raises ReadOnlyViolation before a single byte is sent. Even a bug in a tool
    cannot make the MCP server change your data.
  * It only talks to the one backend URL you configured: no proxies, no following redirects.
"""

import json
import os
import re
import socket
import urllib.error
import urllib.parse
import urllib.request
from typing import Any

DEFAULT_BASE_URL = "http://127.0.0.1:8000"
DEFAULT_TIMEOUT_SECONDS = 15.0
MAX_RESPONSE_BYTES = 1_000_000

# (HTTP method, path pattern). The ONLY requests this client will ever make.
ALLOWED_REQUESTS = (
    ("GET", re.compile(r"^/applications$")),  # list applications
    ("GET", re.compile(r"^/applications/\d+$")),  # one application
    ("POST", re.compile(r"^/knowledge/search$")),  # search notes (POST only because it carries a body)
)


class BackendError(Exception):
    """The backend could not be reached, or answered with an error. The message is written to be
    shown to the AI model (and the user), so it says what happened and what to do."""

    def __init__(self, message: str, status: int | None = None) -> None:
        super().__init__(message)
        self.status = status  # the HTTP status, or None if there was no response at all


class ReadOnlyViolation(Exception):
    """Code tried to make a request outside ALLOWED_REQUESTS. This is a bug, never a user error."""


def describe_error(status: int, body: Any) -> str:
    """Turn an error response into one readable sentence.

    The backend sends two shapes (see backend/app/main.py):
        {"detail": "Application 5 was not found."}
        {"detail": [{"loc": ["body", "query"], "msg": "Field required"}]}    (validation errors)
    """
    if isinstance(body, dict) and "detail" in body:
        detail = body["detail"]
        if isinstance(detail, str):
            return detail
        if isinstance(detail, list):
            problems = []
            for item in detail:
                if not isinstance(item, dict):
                    continue
                parts = item.get("loc", [])
                if isinstance(parts, list) and parts and parts[0] in ("body", "query", "path", "header", "cookie"):
                    parts = parts[1:]  # drop only the FIRST part: it says where the field is, not which field
                location = ".".join(str(part) for part in parts) if isinstance(parts, list) else ""
                message = item.get("msg") if isinstance(item.get("msg"), str) else "Invalid value"
                problems.append(f"{location}: {message}" if location else message)
            if problems:
                return "; ".join(problems)
    return f"The backend answered HTTP {status}."


class _NoRedirects(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, *args: Any, **kwargs: Any) -> None:
        return None  # urllib then reports the 3xx response as an HTTPError instead of following it


class ApiClient:
    def __init__(
        self,
        base_url: str = DEFAULT_BASE_URL,
        timeout: float = DEFAULT_TIMEOUT_SECONDS,
        max_response_bytes: int = MAX_RESPONSE_BYTES,
    ) -> None:
        if not base_url.lower().startswith(("http://", "https://")):
            raise ValueError(f"The backend URL must start with http:// or https:// (got {base_url!r}).")
        if timeout <= 0:
            raise ValueError("The timeout must be greater than zero.")
        self.base_url = base_url.rstrip("/")
        self._timeout = timeout
        self._max_response_bytes = max_response_bytes
        # ProxyHandler({}) = never use HTTP(S)_PROXY from the environment: this is your own backend.
        self._opener = urllib.request.build_opener(urllib.request.ProxyHandler({}), _NoRedirects())

    @classmethod
    def from_env(cls) -> "ApiClient":
        """Reads CAREER_COPILOT_API_URL and CAREER_COPILOT_TIMEOUT (both optional)."""
        raw_timeout = os.environ.get("CAREER_COPILOT_TIMEOUT", str(DEFAULT_TIMEOUT_SECONDS))
        try:
            timeout = float(raw_timeout)
        except ValueError:
            raise ValueError(f"CAREER_COPILOT_TIMEOUT must be a number of seconds (got {raw_timeout!r}).") from None
        return cls(os.environ.get("CAREER_COPILOT_API_URL", DEFAULT_BASE_URL), timeout)

    # ------------------------------------------------------------------ public

    def get(self, path: str, params: dict[str, Any] | None = None) -> Any:
        return self._request("GET", path, params, None)

    def post(self, path: str, body: dict[str, Any]) -> Any:
        return self._request("POST", path, None, body)

    # ------------------------------------------------------------------ internals

    def _request(self, method: str, path: str, params: dict[str, Any] | None, body: dict[str, Any] | None) -> Any:
        if not any(method == allowed and pattern.match(path) for allowed, pattern in ALLOWED_REQUESTS):
            raise ReadOnlyViolation(f"Refusing {method} {path}: not on the read-only allowlist.")

        query = urllib.parse.urlencode({key: value for key, value in (params or {}).items() if value is not None})
        url = f"{self.base_url}{path}{'?' + query if query else ''}"
        data = json.dumps(body).encode("utf-8") if body is not None else None
        headers = {"Accept": "application/json"}
        if data is not None:
            headers["Content-Type"] = "application/json"
        request = urllib.request.Request(url, data=data, method=method, headers=headers)

        status, raw = self._send(request)
        if len(raw) > self._max_response_bytes:
            raise BackendError("The backend's response was too large to handle.", status)
        try:
            parsed: Any = json.loads(raw) if raw else None
        except ValueError:
            parsed = None
            if 200 <= status < 300:
                raise BackendError(f"The backend answered HTTP {status} but the body was not valid JSON.", status) from None

        if not 200 <= status < 300:
            raise BackendError(describe_error(status, parsed), status)
        return parsed

    def _send(self, request: urllib.request.Request) -> tuple[int, bytes]:
        try:
            with self._opener.open(request, timeout=self._timeout) as response:
                return response.status, response.read(self._max_response_bytes + 1)
        except urllib.error.HTTPError as error:  # must come before URLError: it is a subclass
            return error.code, error.read(self._max_response_bytes + 1)
        except urllib.error.URLError as error:
            if isinstance(error.reason, (socket.timeout, TimeoutError)):
                raise self._timeout_error() from None
            raise self._unreachable_error() from None
        except (socket.timeout, TimeoutError):
            raise self._timeout_error() from None
        except OSError:  # connection reset halfway, and similar
            raise self._unreachable_error() from None

    def _unreachable_error(self) -> BackendError:
        return BackendError(
            f"Cannot reach the Career Copilot backend at {self.base_url}. "
            "Start it first (from the backend folder: uvicorn app.main:app) and try again."
        )

    def _timeout_error(self) -> BackendError:
        return BackendError(f"The backend did not answer within {self._timeout:g} seconds.")
