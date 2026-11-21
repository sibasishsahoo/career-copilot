"""The agent's read-only tracker tools, against a real (in-memory) database."""

import json

from sqlalchemy import func, select

from app.models.application import Application, StatusChange
from app.schemas.application import ApplicationCreate, MatchSnapshotCreate, StatusChangeCreate
from app.services import application_service as tracker
from app.services.agent.builtin_tools import build_registry
from app.services.agent.knowledge_tools import KnowledgeProvider
from app.services.agent.tools import ToolRegistry, execute_tool
from app.services.agent.tracker_tools import build_get_application_tool, build_list_applications_tool
from app.services.rag.embedder import HashingEmbedder
from app.services.rag.vector_store import InMemoryVectorStore


def new_app(db, company, title="Backend Engineer", status="wishlist", **extra):
    return tracker.create_application(
        db, ApplicationCreate(company=company, job_title=title, status=status, **extra)
    )


def run(db, tool_name, **arguments):
    registry = ToolRegistry([build_list_applications_tool(db), build_get_application_tool(db)])
    outcome = execute_tool(registry, tool_name, arguments)
    return outcome, (json.loads(outcome.observation) if outcome.ok else None)


# ======================= list_applications =======================

def test_it_lists_applications_newest_update_first(db):
    new_app(db, "First")
    new_app(db, "Second")
    outcome, data = run(db, "list_applications")
    assert outcome.ok
    assert data["count"] == 2
    assert [a["company"] for a in data["applications"]] == ["Second", "First"]


def test_each_entry_has_the_fields_the_prompt_promises(db):
    new_app(db, "Acme", "Data Engineer", location="Remote", applied_date="2026-10-01", status="applied")
    _, data = run(db, "list_applications")
    entry = data["applications"][0]
    assert set(entry) == {"id", "company", "job_title", "status", "location", "applied_date", "updated_at"}
    assert entry["status"] == "applied" and entry["applied_date"] == "2026-10-01" and entry["location"] == "Remote"


def test_it_filters_by_status_ignoring_case(db):
    new_app(db, "Wish Co")
    new_app(db, "Applied Co", status="applied")
    _, data = run(db, "list_applications", status="Applied")
    assert [a["company"] for a in data["applications"]] == ["Applied Co"]


def test_it_searches_company_and_title(db):
    new_app(db, "Acme Corp", "Backend Engineer")
    new_app(db, "Globex", "Data Scientist")
    _, by_company = run(db, "list_applications", search="acme")
    _, by_title = run(db, "list_applications", search="scientist")
    assert [a["company"] for a in by_company["applications"]] == ["Acme Corp"]
    assert [a["company"] for a in by_title["applications"]] == ["Globex"]


def test_the_default_limit_is_ten_and_it_can_be_changed(db):
    for number in range(12):
        new_app(db, f"Company {number}")
    assert run(db, "list_applications")[1]["count"] == 10
    assert run(db, "list_applications", limit=3)[1]["count"] == 3


def test_an_empty_tracker_gives_an_empty_list(db):
    assert run(db, "list_applications")[1] == {"count": 0, "applications": []}


def test_an_unknown_status_is_an_error_that_lists_the_choices(db):
    outcome, _ = run(db, "list_applications", status="ghosted")
    assert outcome.ok is False
    assert "'status' must be one of: wishlist, applied, interviewing, offer, rejected, withdrawn" in outcome.observation


def test_bad_limits_are_rejected(db):
    assert run(db, "list_applications", limit=0)[0].ok is False
    assert run(db, "list_applications", limit=26)[0].ok is False


# ======================= get_application =======================

def test_it_returns_the_details_history_and_saved_match(db):
    application = new_app(db, "Acme", job_url="https://example.com/1", notes="Referred by Sam")
    tracker.change_status(db, application.id, StatusChangeCreate(status="applied", note="Applied online"))
    tracker.attach_match(
        db,
        application.id,
        MatchSnapshotCreate(
            job_description="We need Python and SQL.",
            score=72,
            matched_skills=[{"skill": "Python", "category": "required"}],
            missing_skills=[{"skill": "Docker", "category": "preferred"}],
        ),
    )
    outcome, data = run(db, "get_application", id=application.id)
    assert outcome.ok
    assert data["company"] == "Acme" and data["status"] == "applied"
    assert data["job_url"] == "https://example.com/1" and data["notes"] == "Referred by Sam"
    assert [(h["from"], h["to"], h["note"]) for h in data["status_history"]] == [
        (None, "wishlist", None),
        ("wishlist", "applied", "Applied online"),
    ]
    assert data["saved_match"]["score"] == 72
    assert data["saved_match"]["matched_skills"] == [{"skill": "Python", "category": "required"}]
    assert data["saved_match"]["missing_skills"] == [{"skill": "Docker", "category": "preferred"}]
    assert data["saved_match"]["job_description_excerpt"] == "We need Python and SQL."


def test_an_application_without_a_saved_match_says_null(db):
    application = new_app(db, "Acme")
    assert run(db, "get_application", id=application.id)[1]["saved_match"] is None


def test_long_texts_are_shortened(db):
    application = new_app(db, "Acme", notes="n" * 2000)
    tracker.attach_match(
        db,
        application.id,
        MatchSnapshotCreate(job_description="j" * 5000, score=50, matched_skills=[], missing_skills=[]),
    )
    data = run(db, "get_application", id=application.id)[1]
    assert len(data["notes"]) == 803 and data["notes"].endswith("...")
    assert len(data["saved_match"]["job_description_excerpt"]) == 603


def test_an_unknown_id_is_an_error_the_model_can_read(db):
    outcome, _ = run(db, "get_application", id=999)
    assert outcome.ok is False
    assert outcome.observation == "Error: Application 999 was not found."


def test_the_id_must_be_a_positive_integer(db):
    assert run(db, "get_application", id=0)[0].ok is False
    assert run(db, "get_application", id="abc")[0].ok is False
    assert run(db, "get_application")[0].ok is False


def test_the_id_may_arrive_as_text(db):
    application = new_app(db, "Acme")
    assert run(db, "get_application", id=str(application.id))[0].ok is True


# ======================= the whole toolbox =======================

def provider() -> KnowledgeProvider:
    return lambda: (InMemoryVectorStore(), HashingEmbedder())


def test_the_toolbox_contains_exactly_the_three_read_tools(db):
    registry = build_registry(db, provider(), None)
    assert registry.names == ["search_knowledge", "list_applications", "get_application"]


def test_no_tool_can_change_data(db):
    names = build_registry(db, provider(), None).names
    forbidden = ("create", "update", "delete", "remove", "change", "set", "add", "write", "save")
    assert not [name for name in names if name.startswith(forbidden)]


def test_running_the_tools_never_modifies_the_database(db):
    application = new_app(db, "Acme")
    before = (
        db.scalar(select(func.count()).select_from(Application)),
        db.scalar(select(func.count()).select_from(StatusChange)),
        application.updated_at,
    )
    run(db, "list_applications")
    run(db, "get_application", id=application.id)
    run(db, "get_application", id=999)
    db.expire_all()
    after = (
        db.scalar(select(func.count()).select_from(Application)),
        db.scalar(select(func.count()).select_from(StatusChange)),
        db.get(Application, application.id).updated_at,
    )
    assert before == after
