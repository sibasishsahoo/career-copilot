"""Tests of the /applications HTTP endpoints, end to end (request -> database -> response)."""

import copy
import json
import time
from contextlib import contextmanager

from fastapi.testclient import TestClient
from sqlalchemy import func, select

from app.api.deps import get_llm
from app.db.base import Base
from app.db.session import create_db_engine, get_db, make_session_factory
from app.main import app
from app.models.application import MatchSnapshot, StatusChange
from app.services.job.prompts import EXAMPLE_JOB
from app.services.resume.prompts import EXAMPLE_RESUME
from tests.fakes import ScriptedLLM

SNAPSHOT = {
    "job_description": "We need a backend engineer with Python and SQL experience.",
    "score": 72,
    "matched_skills": [{"skill": "Python", "category": "required"}],
    "missing_skills": [{"skill": "Docker", "category": "preferred"}],
}


def create(client, company="Acme", job_title="Backend Engineer", **extra) -> dict:
    response = client.post("/applications", json={"company": company, "job_title": job_title, **extra})
    assert response.status_code == 201, response.text
    return response.json()


def set_status(client, application_id, status, note=None):
    body = {"status": status}
    if note:
        body["note"] = note
    return client.post(f"/applications/{application_id}/status", json=body)


def tick():
    time.sleep(0.02)


# ======================= POST /applications =======================

def test_create_returns_201_with_full_detail(client):
    response = client.post("/applications", json={"company": "Acme", "job_title": "Backend Engineer"})
    assert response.status_code == 201
    body = response.json()
    assert isinstance(body["id"], int)
    assert body["company"] == "Acme"
    assert body["status"] == "wishlist"
    assert body["match_snapshot"] is None
    assert body["created_at"].endswith(("Z", "+00:00"))  # timezone is included
    assert len(body["status_history"]) == 1
    assert body["status_history"][0]["from_status"] is None
    assert body["status_history"][0]["to_status"] == "wishlist"


def test_create_with_all_fields(client):
    body = create(
        client,
        status="applied",
        job_url="https://example.com/jobs/1",
        location="Remote",
        applied_date="2026-10-01",
        notes="Referred by a friend",
    )
    assert body["status"] == "applied"
    assert body["job_url"] == "https://example.com/jobs/1"
    assert body["location"] == "Remote"
    assert body["applied_date"] == "2026-10-01"
    assert body["notes"] == "Referred by a friend"
    assert body["status_history"][0]["to_status"] == "applied"


def test_create_trims_whitespace(client):
    assert create(client, company="  Acme  ")["company"] == "Acme"


def test_create_requires_company(client):
    assert client.post("/applications", json={"job_title": "Dev"}).status_code == 422


def test_create_requires_job_title(client):
    assert client.post("/applications", json={"company": "Acme"}).status_code == 422


def test_create_rejects_empty_and_blank_company(client):
    for company in ["", "   "]:
        response = client.post("/applications", json={"company": company, "job_title": "Dev"})
        assert response.status_code == 422


def test_create_rejects_overlong_company(client):
    response = client.post("/applications", json={"company": "x" * 201, "job_title": "Dev"})
    assert response.status_code == 422


def test_create_rejects_unknown_status(client):
    response = client.post(
        "/applications", json={"company": "Acme", "job_title": "Dev", "status": "ghosted"}
    )
    assert response.status_code == 422


def test_create_rejects_non_http_urls(client):
    for url in ["javascript:alert(1)", "ftp://example.com/job", "example.com/job", ""]:
        response = client.post(
            "/applications", json={"company": "Acme", "job_title": "Dev", "job_url": url}
        )
        assert response.status_code == 422, url


def test_create_rejects_invalid_date(client):
    response = client.post(
        "/applications", json={"company": "Acme", "job_title": "Dev", "applied_date": "not-a-date"}
    )
    assert response.status_code == 422


def test_create_rejects_unknown_fields(client):
    response = client.post(
        "/applications", json={"company": "Acme", "job_title": "Dev", "salary": 100000}
    )
    assert response.status_code == 422


# ======================= GET /applications/{id} =======================

def test_get_returns_the_same_detail_as_create(client):
    created = create(client)
    response = client.get(f"/applications/{created['id']}")
    assert response.status_code == 200
    assert response.json() == created


def test_get_unknown_id_returns_404(client):
    response = client.get("/applications/999")
    assert response.status_code == 404
    assert response.json()["detail"] == "Application 999 was not found."


def test_get_non_integer_id_returns_422(client):
    assert client.get("/applications/abc").status_code == 422


# ======================= GET /applications =======================

def test_list_is_empty_at_first(client):
    response = client.get("/applications")
    assert response.status_code == 200
    assert response.json() == []


def test_list_returns_summaries_most_recent_first(client):
    for company in ["First", "Second", "Third"]:
        create(client, company)
    items = client.get("/applications").json()
    assert [item["company"] for item in items] == ["Third", "Second", "First"]
    assert "status_history" not in items[0]  # lists stay lightweight
    assert "match_snapshot" not in items[0]


def test_list_order_follows_updates(client):
    first = create(client, "First")
    create(client, "Second")
    tick()
    set_status(client, first["id"], "applied")
    assert client.get("/applications").json()[0]["company"] == "First"


def test_list_filters_by_status(client):
    create(client, "Wish Co")
    create(client, "Applied Co", status="applied")
    items = client.get("/applications", params={"status": "applied"}).json()
    assert [item["company"] for item in items] == ["Applied Co"]


def test_list_searches_company_and_title(client):
    create(client, "Acme Corp", "Backend Engineer")
    create(client, "Globex", "Data Scientist")
    by_company = client.get("/applications", params={"search": "acme"}).json()
    by_title = client.get("/applications", params={"search": "scientist"}).json()
    assert [item["company"] for item in by_company] == ["Acme Corp"]
    assert [item["company"] for item in by_title] == ["Globex"]


def test_list_pagination(client):
    for number in range(5):
        create(client, f"Company {number}")
    assert len(client.get("/applications", params={"limit": 2}).json()) == 2
    assert len(client.get("/applications", params={"limit": 10, "offset": 4}).json()) == 1


def test_list_rejects_bad_query_parameters(client):
    for params in [
        {"status": "ghosted"},
        {"limit": 0},
        {"limit": 201},
        {"offset": -1},
        {"search": "x" * 101},
    ]:
        assert client.get("/applications", params=params).status_code == 422, params


# ======================= PATCH /applications/{id} =======================

def test_patch_changes_only_the_fields_sent(client):
    created = create(client, location="Remote", notes="keep me")
    response = client.patch(f"/applications/{created['id']}", json={"company": "Globex"})
    assert response.status_code == 200
    body = response.json()
    assert body["company"] == "Globex"
    assert body["location"] == "Remote"
    assert body["notes"] == "keep me"
    assert len(body["status_history"]) == 1  # editing details never touches the history


def test_patch_null_clears_an_optional_field(client):
    created = create(client, location="Remote")
    response = client.patch(f"/applications/{created['id']}", json={"location": None})
    assert response.json()["location"] is None


def test_patch_cannot_null_required_fields(client):
    created = create(client)
    for field in ["company", "job_title"]:
        response = client.patch(f"/applications/{created['id']}", json={field: None})
        assert response.status_code == 422, field


def test_patch_cannot_change_status(client):
    created = create(client)
    response = client.patch(f"/applications/{created['id']}", json={"status": "applied"})
    assert response.status_code == 422
    assert client.get(f"/applications/{created['id']}").json()["status"] == "wishlist"


def test_patch_rejects_bad_url(client):
    created = create(client)
    response = client.patch(f"/applications/{created['id']}", json={"job_url": "javascript:alert(1)"})
    assert response.status_code == 422


def test_patch_with_empty_body_changes_nothing(client):
    created = create(client)
    response = client.patch(f"/applications/{created['id']}", json={})
    assert response.status_code == 200
    assert response.json() == created


def test_patch_bumps_updated_at(client):
    created = create(client)
    tick()
    updated = client.patch(f"/applications/{created['id']}", json={"notes": "hello"}).json()
    assert updated["updated_at"] > created["updated_at"]
    assert updated["created_at"] == created["created_at"]


def test_patch_unknown_id_returns_404(client):
    assert client.patch("/applications/999", json={"notes": "x"}).status_code == 404


# ======================= POST /applications/{id}/status =======================

def test_status_change_is_recorded_in_history(client):
    created = create(client)
    response = set_status(client, created["id"], "applied", note="Applied on the company site")
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "applied"
    assert len(body["status_history"]) == 2
    latest = body["status_history"][-1]
    assert latest["from_status"] == "wishlist"
    assert latest["to_status"] == "applied"
    assert latest["note"] == "Applied on the company site"


def test_status_change_is_saved(client):
    created = create(client)
    set_status(client, created["id"], "interviewing")
    assert client.get(f"/applications/{created['id']}").json()["status"] == "interviewing"


def test_a_full_pipeline_is_recorded_in_order(client):
    created = create(client)
    for status in ["applied", "interviewing", "offer"]:
        set_status(client, created["id"], status)
    history = client.get(f"/applications/{created['id']}").json()["status_history"]
    assert [h["to_status"] for h in history] == ["wishlist", "applied", "interviewing", "offer"]
    assert [h["from_status"] for h in history] == [None, "wishlist", "applied", "interviewing"]


def test_same_status_adds_no_history(client):
    created = create(client)
    response = set_status(client, created["id"], "wishlist")
    assert response.status_code == 200
    assert len(response.json()["status_history"]) == 1


def test_rejected_application_can_be_reopened(client):
    created = create(client, status="rejected")
    response = set_status(client, created["id"], "interviewing", note="They came back")
    assert response.status_code == 200
    assert response.json()["status"] == "interviewing"


def test_status_change_bumps_updated_at(client):
    created = create(client)
    tick()
    updated = set_status(client, created["id"], "applied").json()
    assert updated["updated_at"] > created["updated_at"]


def test_status_change_rejects_unknown_status(client):
    created = create(client)
    assert set_status(client, created["id"], "ghosted").status_code == 422


def test_status_change_requires_a_status(client):
    created = create(client)
    assert client.post(f"/applications/{created['id']}/status", json={}).status_code == 422


def test_status_change_unknown_application_returns_404(client):
    assert set_status(client, 999, "applied").status_code == 404


# ======================= PUT/DELETE /applications/{id}/match =======================

def test_attach_match_returns_the_snapshot(client):
    created = create(client)
    response = client.put(f"/applications/{created['id']}/match", json=SNAPSHOT)
    assert response.status_code == 200
    body = response.json()
    assert body["score"] == 72
    assert body["job_description"] == SNAPSHOT["job_description"]
    assert body["matched_skills"] == SNAPSHOT["matched_skills"]
    assert body["missing_skills"] == SNAPSHOT["missing_skills"]
    assert body["attached_at"].endswith(("Z", "+00:00"))


def test_attached_match_appears_in_the_application_detail(client):
    created = create(client)
    client.put(f"/applications/{created['id']}/match", json=SNAPSHOT)
    detail = client.get(f"/applications/{created['id']}").json()
    assert detail["match_snapshot"]["score"] == 72
    assert detail["match_snapshot"]["missing_skills"] == [{"skill": "Docker", "category": "preferred"}]


def test_attaching_again_replaces_the_snapshot(client, session_factory):
    created = create(client)
    client.put(f"/applications/{created['id']}/match", json=SNAPSHOT)
    client.put(f"/applications/{created['id']}/match", json={**SNAPSHOT, "score": 15})

    assert client.get(f"/applications/{created['id']}").json()["match_snapshot"]["score"] == 15
    with session_factory() as session:
        assert session.scalar(select(func.count()).select_from(MatchSnapshot)) == 1


def test_attach_match_bumps_application_updated_at(client):
    created = create(client)
    tick()
    client.put(f"/applications/{created['id']}/match", json=SNAPSHOT)
    assert client.get(f"/applications/{created['id']}").json()["updated_at"] > created["updated_at"]


def test_attach_match_rejects_invalid_bodies(client):
    created = create(client)
    url = f"/applications/{created['id']}/match"
    bad_bodies = {
        "score too high": {**SNAPSHOT, "score": 101},
        "score negative": {**SNAPSHOT, "score": -1},
        "missing job_description": {k: v for k, v in SNAPSHOT.items() if k != "job_description"},
        "empty job_description": {**SNAPSHOT, "job_description": ""},
        "missing missing_skills": {k: v for k, v in SNAPSHOT.items() if k != "missing_skills"},
        "bad category": {**SNAPSHOT, "matched_skills": [{"skill": "Python", "category": "optional"}]},
        "skills not a list": {**SNAPSHOT, "matched_skills": "Python"},
    }
    for label, body in bad_bodies.items():
        assert client.put(url, json=body).status_code == 422, label


def test_attach_match_refuses_a_resume_field(client):
    """Privacy: the endpoint rejects resume data instead of silently ignoring it."""
    created = create(client)
    response = client.put(
        f"/applications/{created['id']}/match",
        json={**SNAPSHOT, "resume": {"full_name": "Jane Doe"}},
    )
    assert response.status_code == 422
    assert response.json()["detail"][0]["type"] == "extra_forbidden"


def test_attach_match_unknown_application_returns_404(client):
    assert client.put("/applications/999/match", json=SNAPSHOT).status_code == 404


def test_remove_match(client):
    created = create(client)
    client.put(f"/applications/{created['id']}/match", json=SNAPSHOT)
    response = client.delete(f"/applications/{created['id']}/match")
    assert response.status_code == 204
    assert client.get(f"/applications/{created['id']}").json()["match_snapshot"] is None


def test_remove_match_when_none_attached_returns_404(client):
    created = create(client)
    assert client.delete(f"/applications/{created['id']}/match").status_code == 404


# ======================= DELETE /applications/{id} =======================

def test_delete_returns_204_and_removes_the_application(client):
    created = create(client)
    response = client.delete(f"/applications/{created['id']}")
    assert response.status_code == 204
    assert response.content == b""
    assert client.get(f"/applications/{created['id']}").status_code == 404
    assert client.get("/applications").json() == []


def test_delete_also_removes_history_and_snapshot(client, session_factory):
    created = create(client)
    set_status(client, created["id"], "applied")
    client.put(f"/applications/{created['id']}/match", json=SNAPSHOT)
    client.delete(f"/applications/{created['id']}")

    with session_factory() as session:
        assert session.scalar(select(func.count()).select_from(StatusChange)) == 0
        assert session.scalar(select(func.count()).select_from(MatchSnapshot)) == 0


def test_delete_unknown_id_returns_404(client):
    assert client.delete("/applications/999").status_code == 404


def test_snapshot_routes_after_delete_return_404(client):
    created = create(client)
    client.delete(f"/applications/{created['id']}")
    assert client.put(f"/applications/{created['id']}/match", json=SNAPSHOT).status_code == 404
    assert set_status(client, created["id"], "applied").status_code == 404


# ======================= persistence across "server restarts" =======================

@contextmanager
def client_for_database_file(url):
    """Start a fresh engine + client on a database FILE, like a freshly started server."""
    engine = create_db_engine(url)
    Base.metadata.create_all(engine)  # what init_db() does at startup
    factory = make_session_factory(engine)

    def override_get_db():
        session = factory()
        try:
            yield session
        finally:
            session.close()

    app.dependency_overrides[get_db] = override_get_db
    try:
        yield TestClient(app)
    finally:
        app.dependency_overrides.pop(get_db, None)
        engine.dispose()


def test_data_survives_a_server_restart(tmp_path):
    url = f"sqlite:///{(tmp_path / 'restart.db').as_posix()}"

    with client_for_database_file(url) as first_run:
        created = create(first_run, "Persisted Co", "Platform Engineer", notes="remember me")
        set_status(first_run, created["id"], "interviewing", note="Phone screen")
        first_run.put(f"/applications/{created['id']}/match", json=SNAPSHOT)
        before_restart = first_run.get(f"/applications/{created['id']}").json()

    # the first engine is gone; a new one opens the same file
    with client_for_database_file(url) as second_run:
        after_restart = second_run.get(f"/applications/{created['id']}").json()
        assert after_restart == before_restart
        assert after_restart["company"] == "Persisted Co"
        assert after_restart["status"] == "interviewing"
        assert after_restart["match_snapshot"]["score"] == 72
        assert [h["to_status"] for h in after_restart["status_history"]] == ["wishlist", "interviewing"]
        assert len(second_run.get("/applications").json()) == 1


# ======================= Phase 3 -> Phase 4, and the privacy rule =======================

JOB_TEXT = "We are hiring a Backend Engineer. Requirements: Python, SQL, REST APIs. Nice to have: Docker, AWS."


def all_database_text(session_factory) -> str:
    """Every value of every row of every table, as one big string."""
    chunks = []
    with session_factory() as session:
        for table in Base.metadata.sorted_tables:
            for row in session.execute(select(table)).all():
                chunks.append(repr(tuple(row)))
    return "\n".join(chunks)


def test_match_result_can_be_saved_on_an_application_without_storing_the_resume(client, session_factory):
    # 1. Run a real Phase 3 match (the LLM is replaced by a scripted fake).
    llm = ScriptedLLM([json.dumps(EXAMPLE_JOB), json.dumps({"suggestions": ["Learn Docker."]})])
    app.dependency_overrides[get_llm] = lambda: llm
    match_response = client.post(
        "/jobs/match",
        json={"resume": copy.deepcopy(EXAMPLE_RESUME), "job_description": JOB_TEXT},
    )
    assert match_response.status_code == 200
    match = match_response.json()

    # 2. Track an application and attach the match - only the agreed fields, never the resume.
    application = create(client, "Acme Corp", "Backend Engineer", status="applied")
    payload = {
        "job_description": JOB_TEXT,
        "score": match["score"],
        "matched_skills": [
            {"skill": hit["skill"], "category": "required"} for hit in match["required"]["matched"]
        ]
        + [{"skill": hit["skill"], "category": "preferred"} for hit in match["preferred"]["matched"]],
        "missing_skills": [{"skill": s, "category": "required"} for s in match["required"]["missing"]]
        + [{"skill": s, "category": "preferred"} for s in match["preferred"]["missing"]],
    }
    attach_response = client.put(f"/applications/{application['id']}/match", json=payload)
    assert attach_response.status_code == 200

    detail = client.get(f"/applications/{application['id']}").json()
    assert detail["match_snapshot"]["score"] == match["score"] == 47
    assert {"skill": "REST APIs", "category": "required"} in detail["match_snapshot"]["missing_skills"]

    # 3. Privacy: nothing from the resume reached the database.
    stored = all_database_text(session_factory)
    assert JOB_TEXT in stored and "REST APIs" in stored  # the dump works, and job data is there
    assert "Jane Doe" not in stored  # resume: name
    assert "Built a billing API" not in stored  # resume: bullet point
    assert "Backend engineer with 5 years" not in stored  # resume: summary
