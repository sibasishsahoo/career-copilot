"""The MCP tool logic (mcp_server/tools.py) against a fake API object: no HTTP, no MCP SDK."""

import json

import pytest

from mcp_server import tools
from mcp_server.api_client import ApiClient, BackendError
from mcp_server.tools import ToolInputError
from tests.fake_backend import fake_backend

DETAIL = {
    "id": 7, "company": "Acme", "job_title": "Backend Engineer", "status": "applied",
    "job_url": "https://example.com/jobs/1", "location": "Remote", "applied_date": "2026-10-01",
    "notes": "Referred by Sam", "created_at": "2026-10-01T09:00:00Z", "updated_at": "2026-10-02T10:00:00Z",
    "status_history": [
        {"id": 1, "from_status": None, "to_status": "wishlist", "note": None, "changed_at": "2026-10-01T09:00:00Z"},
        {"id": 2, "from_status": "wishlist", "to_status": "applied", "note": "Applied online", "changed_at": "2026-10-02T10:00:00Z"},
    ],
    "match_snapshot": {
        "id": 1, "job_description": "We need Python and SQL.", "score": 72,
        "matched_skills": [{"skill": "Python", "category": "required"}],
        "missing_skills": [{"skill": "Docker", "category": "preferred"}],
        "attached_at": "2026-10-03T08:00:00Z",
    },
}
LIST_ITEM = {k: v for k, v in DETAIL.items() if k not in ("status_history", "match_snapshot")}


class FakeApi:
    """Answers from a dict and remembers every call. Calls it does not know about raise KeyError."""

    def __init__(self, responses):
        self.responses = responses
        self.calls = []

    def get(self, path, params=None):
        self.calls.append(("GET", path, params))
        return self.responses[("GET", path)]

    def post(self, path, body):
        self.calls.append(("POST", path, body))
        return self.responses[("POST", path)]


def input_error(function, *args, **kwargs) -> str:
    with pytest.raises(ToolInputError) as excinfo:
        function(*args, **kwargs)
    return str(excinfo.value)


# ======================= list_applications =======================

def test_the_default_call_only_sends_the_limit():
    api = FakeApi({("GET", "/applications"): [LIST_ITEM]})
    tools.list_applications(api)
    assert api.calls == [("GET", "/applications", {"status": None, "search": None, "limit": 10})]


def test_arguments_are_cleaned_before_they_are_sent():
    api = FakeApi({("GET", "/applications"): []})
    tools.list_applications(api, status=" Applied ", search="  acme  ", limit="3")
    assert api.calls[0][2] == {"status": "applied", "search": "acme", "limit": 3}


def test_a_blank_status_or_search_means_no_filter():
    api = FakeApi({("GET", "/applications"): []})
    tools.list_applications(api, status="  ", search="")
    assert api.calls[0][2] == {"status": None, "search": None, "limit": 10}


def test_entries_are_reduced_to_the_summary_fields():
    api = FakeApi({("GET", "/applications"): [LIST_ITEM]})
    result = tools.list_applications(api)
    assert result["count"] == 1
    assert result["applications"][0] == {
        "id": 7, "company": "Acme", "job_title": "Backend Engineer", "status": "applied",
        "location": "Remote", "applied_date": "2026-10-01", "updated_at": "2026-10-02T10:00:00Z",
    }


def test_an_empty_tracker_gives_an_empty_list():
    assert tools.list_applications(FakeApi({("GET", "/applications"): []})) == {"count": 0, "applications": []}


def test_a_bad_status_lists_the_choices_and_sends_nothing():
    api = FakeApi({})
    message = input_error(tools.list_applications, api, status="ghosted")
    assert "wishlist, applied, interviewing, offer, rejected, withdrawn" in message
    assert api.calls == []


def test_limit_must_be_a_whole_number_in_range():
    api = FakeApi({})
    for bad in [0, 26, -1, True, "many", 2.5, None]:
        assert "'limit'" in input_error(tools.list_applications, api, limit=bad)
    assert api.calls == []
    assert FakeApi({("GET", "/applications"): []}).get("/applications") == []  # the fake itself works


def test_limit_accepts_the_edges_and_whole_floats():
    api = FakeApi({("GET", "/applications"): []})
    tools.list_applications(api, limit=1)
    tools.list_applications(api, limit=25)
    tools.list_applications(api, limit=5.0)
    assert [call[2]["limit"] for call in api.calls] == [1, 25, 5]


def test_search_text_is_length_limited():
    assert "'search' must be at most 100 characters" in input_error(tools.list_applications, FakeApi({}), search="x" * 101)
    assert "'search' must be a string" in input_error(tools.list_applications, FakeApi({}), search=5)


def test_a_malformed_answer_from_the_backend_is_reported():
    with pytest.raises(BackendError, match="unexpected response"):
        tools.list_applications(FakeApi({("GET", "/applications"): {"oops": 1}}))


# ======================= get_application =======================

def test_it_fetches_the_application_by_id():
    api = FakeApi({("GET", "/applications/7"): DETAIL})
    tools.get_application(api, 7)
    assert api.calls == [("GET", "/applications/7", None)]


def test_the_result_has_details_history_and_saved_match():
    result = tools.get_application(FakeApi({("GET", "/applications/7"): DETAIL}), 7)
    assert result["company"] == "Acme" and result["status"] == "applied"
    assert result["job_url"] == "https://example.com/jobs/1" and result["notes"] == "Referred by Sam"
    assert result["status_history"] == [
        {"from": None, "to": "wishlist", "note": None, "at": "2026-10-01T09:00:00Z"},
        {"from": "wishlist", "to": "applied", "note": "Applied online", "at": "2026-10-02T10:00:00Z"},
    ]
    assert result["saved_match"] == {
        "score": 72,
        "matched_skills": [{"skill": "Python", "category": "required"}],
        "missing_skills": [{"skill": "Docker", "category": "preferred"}],
        "job_description_excerpt": "We need Python and SQL.",
    }


def test_no_saved_match_gives_null():
    detail = {**DETAIL, "match_snapshot": None}
    assert tools.get_application(FakeApi({("GET", "/applications/7"): detail}), 7)["saved_match"] is None


def test_long_texts_are_shortened():
    detail = {**DETAIL, "notes": "n" * 2000, "match_snapshot": {**DETAIL["match_snapshot"], "job_description": "j" * 5000}}
    result = tools.get_application(FakeApi({("GET", "/applications/7"): detail}), 7)
    assert len(result["notes"]) == 803 and result["notes"].endswith("...")
    assert len(result["saved_match"]["job_description_excerpt"]) == 603


def test_the_id_may_arrive_as_text_but_must_be_a_positive_integer():
    api = FakeApi({("GET", "/applications/7"): DETAIL})
    tools.get_application(api, "7")
    assert api.calls[0][1] == "/applications/7"
    for bad in [0, -3, "abc", "1.5", True, None, "../knowledge/documents"]:
        assert "'application_id'" in input_error(tools.get_application, FakeApi({}), bad)


def test_backend_errors_pass_through_with_their_message():
    routes = {("GET", "/applications/999"): (404, {"detail": "Application 999 was not found."})}
    with fake_backend(routes) as backend:
        with pytest.raises(BackendError, match="Application 999 was not found.") as excinfo:
            tools.get_application(ApiClient(backend.url), 999)
        assert excinfo.value.status == 404


# ======================= search_knowledge =======================

RESULTS = {
    "query": "deploy",
    "results": [
        {"rank": 1, "score": 0.61, "doc_id": "a", "title": "Faster deployments", "chunk_index": 0, "text": "Cut deploys to 12 min."},
        {"rank": 2, "score": 0.18, "doc_id": "b", "title": "Mentoring", "chunk_index": 1, "text": "Mentored two interns."},
    ],
}


def test_the_search_posts_the_query_and_k():
    api = FakeApi({("POST", "/knowledge/search"): RESULTS})
    tools.search_knowledge(api, "  deployment time  ", k="4")
    assert api.calls == [("POST", "/knowledge/search", {"query": "deployment time", "k": 4})]


def test_the_default_k_is_three():
    api = FakeApi({("POST", "/knowledge/search"): RESULTS})
    tools.search_knowledge(api, "deploy")
    assert api.calls[0][2]["k"] == 3


def test_matches_have_the_note_title_score_and_text():
    result = tools.search_knowledge(FakeApi({("POST", "/knowledge/search"): RESULTS}), "deploy")
    assert result["count"] == 2
    assert result["matches"][0] == {"note": "Faster deployments", "score": 0.61, "text": "Cut deploys to 12 min."}
    assert [m["note"] for m in result["matches"]] == ["Faster deployments", "Mentoring"]  # order kept


def test_min_score_filters_weak_matches():
    result = tools.search_knowledge(FakeApi({("POST", "/knowledge/search"): RESULTS}), "deploy", min_score=0.25)
    assert [m["note"] for m in result["matches"]] == ["Faster deployments"]


def test_nothing_above_the_threshold_says_so():
    result = tools.search_knowledge(FakeApi({("POST", "/knowledge/search"): RESULTS}), "deploy", min_score=0.9)
    assert result == {"count": 0, "matches": [], "message": "No notes matched this query."}


def test_an_empty_knowledge_base_says_so():
    result = tools.search_knowledge(FakeApi({("POST", "/knowledge/search"): {"query": "x", "results": []}}), "x")
    assert result["count"] == 0 and result["message"] == "No notes matched this query."


def test_search_arguments_are_validated_before_anything_is_sent():
    api = FakeApi({})
    assert "'query' is required" in input_error(tools.search_knowledge, api, None)
    assert "'query' must not be empty" in input_error(tools.search_knowledge, api, "   ")
    assert "'query' must be at most 500 characters" in input_error(tools.search_knowledge, api, "x" * 501)
    assert "'query' must be a string" in input_error(tools.search_knowledge, api, 42)
    for bad_k in [0, 6, "lots", True]:
        assert "'k'" in input_error(tools.search_knowledge, api, "ok", k=bad_k)
    for bad_score in [-0.1, 1.1, "high", True, None]:
        assert "'min_score' must be a number between 0 and 1" in input_error(tools.search_knowledge, api, "ok", min_score=bad_score)
    assert api.calls == []


def test_a_malformed_search_answer_is_reported():
    with pytest.raises(BackendError, match="unexpected response"):
        tools.search_knowledge(FakeApi({("POST", "/knowledge/search"): {"nope": 1}}), "x")


# ======================= render =======================

def test_render_is_compact_json_that_keeps_non_ascii_readable():
    text = tools.render({"a": [1, 2], "b": "café – résumé"})
    assert text == '{"a":[1,2],"b":"café – résumé"}'
    assert json.loads(text)["b"] == "café – résumé"


# ======================= the prompt template =======================

def test_the_prompt_names_the_application_and_the_tools_to_use():
    prompt = tools.build_interview_prompt("7")
    assert "get_application with application_id 7" in prompt
    assert "search_knowledge" in prompt
    assert "STAR" in prompt
    assert "never claim experience I do not have" in prompt
    assert "Never invent anything about me" in prompt


def test_the_focus_is_added_when_given_and_left_out_otherwise():
    assert "Pay special attention to: system design" in tools.build_interview_prompt(7, "  system design  ")
    assert "Pay special attention" not in tools.build_interview_prompt(7)
    assert "Pay special attention" not in tools.build_interview_prompt(7, "   ")


def test_the_prompt_rejects_bad_ids_and_overlong_focus():
    for bad in ["abc", "0", "-3", "", "1.5", None]:
        assert "'application_id'" in input_error(tools.build_interview_prompt, bad)
    assert "'focus' must be at most 300 characters" in input_error(tools.build_interview_prompt, 1, "x" * 301)


# ======================= everything the tools do is read-only =======================

def test_running_every_tool_only_makes_the_allowed_requests():
    routes = {
        ("GET", "/applications"): (200, [LIST_ITEM]),
        ("GET", "/applications/7"): (200, DETAIL),
        ("POST", "/knowledge/search"): (200, RESULTS),
    }
    with fake_backend(routes) as backend:
        api = ApiClient(backend.url)
        tools.list_applications(api, status="applied", search="acme", limit=5)
        tools.get_application(api, 7)
        tools.search_knowledge(api, "deploy", k=2)
        assert [(r.method, r.target.split("?")[0]) for r in backend.requests] == [
            ("GET", "/applications"), ("GET", "/applications/7"), ("POST", "/knowledge/search"),
        ]
