import os
from contextlib import contextmanager

import pytest

from mcp_server.api_client import ApiClient, BackendError, ReadOnlyViolation, describe_error
from tests.fake_backend import closed_port_url, fake_backend


@contextmanager
def environment(**values):
    """Temporarily set (or remove, with None) environment variables."""
    saved = {name: os.environ.get(name) for name in values}
    try:
        for name, value in values.items():
            if value is None:
                os.environ.pop(name, None)
            else:
                os.environ[name] = value
        yield
    finally:
        for name, value in saved.items():
            if value is None:
                os.environ.pop(name, None)
            else:
                os.environ[name] = value


# ======================= describe_error =======================

def test_a_plain_detail_is_used_as_is():
    assert describe_error(404, {"detail": "Application 5 was not found."}) == "Application 5 was not found."


def test_validation_errors_become_field_colon_message():
    body = {"detail": [{"loc": ["body", "query"], "msg": "Field required", "type": "missing"}]}
    assert describe_error(422, body) == "query: Field required"


def test_several_validation_errors_are_joined_and_nested_locations_kept():
    body = {"detail": [{"loc": ["body", "resume", "name"], "msg": "Too short"}, {"loc": ["query", "limit"], "msg": "Too big"}]}
    assert describe_error(422, body) == "resume.name: Too short; limit: Too big"


def test_an_error_without_a_location_shows_just_the_message():
    assert describe_error(422, {"detail": [{"msg": "Something is off"}]}) == "Something is off"


def test_anything_else_falls_back_to_the_status_code():
    for body in [None, {}, {"detail": []}, {"detail": 5}, "text", [1, 2]]:
        assert describe_error(502, body) == "The backend answered HTTP 502."


# ======================= successful requests =======================

def test_get_returns_the_parsed_json():
    with fake_backend({("GET", "/applications"): (200, [{"id": 1}])}) as backend:
        assert ApiClient(backend.url).get("/applications") == [{"id": 1}]


def test_the_request_asks_for_json():
    with fake_backend({("GET", "/applications"): (200, [])}) as backend:
        ApiClient(backend.url).get("/applications")
        assert backend.requests[0].accept == "application/json"


def test_query_parameters_are_encoded_and_none_values_are_dropped():
    with fake_backend({("GET", "/applications"): (200, [])}) as backend:
        ApiClient(backend.url).get("/applications", {"status": "applied", "search": "acme & co", "limit": 5, "skip": None})
        target = backend.requests[0].target
        assert target.startswith("/applications?")
        assert "status=applied" in target and "limit=5" in target
        assert "search=acme+%26+co" in target
        assert "skip" not in target


def test_no_parameters_means_no_question_mark():
    with fake_backend({("GET", "/applications"): (200, [])}) as backend:
        ApiClient(backend.url).get("/applications", {"status": None})
        assert backend.requests[0].target == "/applications"


def test_post_sends_a_json_body_with_a_content_type():
    with fake_backend({("POST", "/knowledge/search"): (200, {"results": []})}) as backend:
        result = ApiClient(backend.url).post("/knowledge/search", {"query": "café", "k": 3})
        assert result == {"results": []}
        sent = backend.requests[0]
        assert sent.body == {"query": "café", "k": 3}
        assert sent.content_type == "application/json"


def test_a_trailing_slash_on_the_base_url_is_ignored():
    with fake_backend({("GET", "/applications/12"): (200, {"id": 12})}) as backend:
        assert ApiClient(backend.url + "/").get("/applications/12") == {"id": 12}


def test_proxy_settings_in_the_environment_are_ignored():
    with fake_backend({("GET", "/applications"): (200, [])}) as backend:
        with environment(HTTP_PROXY="http://127.0.0.1:9", http_proxy="http://127.0.0.1:9"):
            assert ApiClient(backend.url).get("/applications") == []


# ======================= failures become readable BackendErrors =======================

def test_an_error_response_carries_the_backends_message_and_status():
    routes = {("GET", "/applications/999"): (404, {"detail": "Application 999 was not found."})}
    with fake_backend(routes) as backend:
        with pytest.raises(BackendError, match="Application 999 was not found.") as excinfo:
            ApiClient(backend.url).get("/applications/999")
        assert excinfo.value.status == 404


def test_validation_errors_from_the_backend_are_formatted():
    routes = {("POST", "/knowledge/search"): (422, {"detail": [{"loc": ["body", "query"], "msg": "Field required"}]})}
    with fake_backend(routes) as backend:
        with pytest.raises(BackendError, match="query: Field required"):
            ApiClient(backend.url).post("/knowledge/search", {})


def test_a_server_error_that_is_not_json_still_gives_a_clear_message():
    with fake_backend({("GET", "/applications"): (500, "Internal Server Error")}) as backend:
        with pytest.raises(BackendError, match="answered HTTP 500") as excinfo:
            ApiClient(backend.url).get("/applications")
        assert excinfo.value.status == 500


def test_a_successful_answer_that_is_not_json_is_an_error():
    with fake_backend({("GET", "/applications"): (200, "<html>hello</html>")}) as backend:
        with pytest.raises(BackendError, match="not valid JSON"):
            ApiClient(backend.url).get("/applications")


def test_an_unreachable_backend_says_how_to_start_it():
    url = closed_port_url()
    with pytest.raises(BackendError) as excinfo:
        ApiClient(url).get("/applications")
    assert f"Cannot reach the Career Copilot backend at {url}" in str(excinfo.value)
    assert "uvicorn app.main:app" in str(excinfo.value)
    assert excinfo.value.status is None


def test_a_slow_backend_times_out():
    with fake_backend({("GET", "/applications"): (200, [], {"delay": 1.0})}) as backend:
        with pytest.raises(BackendError, match="did not answer within 0.2 seconds"):
            ApiClient(backend.url, timeout=0.2).get("/applications")


def test_redirects_are_not_followed():
    routes = {("GET", "/applications"): (307, None, {"headers": {"Location": "http://127.0.0.1:9/elsewhere"}})}
    with fake_backend(routes) as backend:
        with pytest.raises(BackendError, match="answered HTTP 307") as excinfo:
            ApiClient(backend.url).get("/applications")
        assert excinfo.value.status == 307
        assert len(backend.requests) == 1


def test_an_oversized_response_is_refused():
    with fake_backend({("GET", "/applications"): (200, [{"text": "x" * 1000}])}) as backend:
        with pytest.raises(BackendError, match="too large"):
            ApiClient(backend.url, max_response_bytes=100).get("/applications")


# ======================= read-only by construction =======================

def test_requests_outside_the_allowlist_are_refused_before_anything_is_sent():
    with fake_backend({}) as backend:
        api = ApiClient(backend.url)
        forbidden = [
            ("get", "/applications/1/status"),
            ("get", "/applications/../knowledge/documents"),
            ("get", "/applications/abc"),
            ("get", "/knowledge/documents"),
            ("get", "/health"),
            ("get", "/applications/1/match"),
            ("post", "/applications"),
            ("post", "/applications/1/status"),
            ("post", "/knowledge/ask"),
            ("post", "/knowledge/documents"),
            ("post", "/jobs/match"),
        ]
        for method, path in forbidden:
            with pytest.raises(ReadOnlyViolation):
                if method == "get":
                    api.get(path)
                else:
                    api.post(path, {})
        assert backend.requests == []  # nothing ever reached the backend


def test_methods_that_change_data_cannot_be_made_at_all():
    with fake_backend({}) as backend:
        api = ApiClient(backend.url)
        for method in ("PUT", "PATCH", "DELETE"):
            for path in ("/applications", "/applications/1", "/knowledge/search"):
                with pytest.raises(ReadOnlyViolation):
                    api._request(method, path, None, None)
        assert backend.requests == []


def test_the_three_allowed_requests_work():
    routes = {
        ("GET", "/applications"): (200, []),
        ("GET", "/applications/12"): (200, {"id": 12}),
        ("POST", "/knowledge/search"): (200, {"results": []}),
    }
    with fake_backend(routes) as backend:
        api = ApiClient(backend.url)
        api.get("/applications")
        api.get("/applications/12")
        api.post("/knowledge/search", {"query": "x", "k": 1})
        assert [(r.method, r.target) for r in backend.requests] == [
            ("GET", "/applications"), ("GET", "/applications/12"), ("POST", "/knowledge/search"),
        ]


# ======================= configuration =======================

def test_the_base_url_must_be_http_or_https():
    for bad in ["ftp://example.com", "127.0.0.1:8000", "file:///etc/passwd", ""]:
        with pytest.raises(ValueError, match="http://"):
            ApiClient(bad)


def test_the_timeout_must_be_positive():
    with pytest.raises(ValueError, match="timeout"):
        ApiClient("http://127.0.0.1:8000", timeout=0)


def test_from_env_uses_defaults_when_nothing_is_set():
    with environment(CAREER_COPILOT_API_URL=None, CAREER_COPILOT_TIMEOUT=None):
        assert ApiClient.from_env().base_url == "http://127.0.0.1:8000"


def test_from_env_reads_the_url_and_timeout():
    with environment(CAREER_COPILOT_API_URL="http://localhost:9000/", CAREER_COPILOT_TIMEOUT="3.5"):
        client = ApiClient.from_env()
        assert client.base_url == "http://localhost:9000"
        assert client._timeout == 3.5


def test_from_env_rejects_a_bad_timeout():
    with environment(CAREER_COPILOT_TIMEOUT="soon"):
        with pytest.raises(ValueError, match="CAREER_COPILOT_TIMEOUT"):
            ApiClient.from_env()
