"""Tests of the tracker logic, called directly (no HTTP)."""

import time
from datetime import date, timezone

import pytest
from pydantic import ValidationError
from sqlalchemy import func, select

from app.db.base import Base
from app.db.session import create_db_engine, make_session_factory
from app.models.application import ApplicationStatus, MatchSnapshot, StatusChange
from app.schemas.application import (
    ApplicationCreate,
    ApplicationUpdate,
    MatchSnapshotCreate,
    StatusChangeCreate,
)
from app.schemas.job import JobAnalysis, MatchResult, SkillGroupResult, SkillMatch
from app.services import application_service as service
from app.services.application_service import ApplicationNotFoundError, MatchSnapshotNotFoundError


def new_app(db, company="Acme", title="Backend Engineer", **extra):
    return service.create_application(db, ApplicationCreate(company=company, job_title=title, **extra))


def move(db, application, status, note=None):
    return service.change_status(db, application.id, StatusChangeCreate(status=status, note=note))


def snapshot_data(score=72, **overrides) -> MatchSnapshotCreate:
    data = dict(
        job_description="We need a backend engineer with Python and SQL experience.",
        score=score,
        matched_skills=[{"skill": "Python", "category": "required"}],
        missing_skills=[{"skill": "Docker", "category": "preferred"}],
    )
    data.update(overrides)
    return MatchSnapshotCreate(**data)


def tick():
    """Wait a moment so two timestamps cannot be identical (Windows clocks are coarse)."""
    time.sleep(0.02)


def count(db, model) -> int:
    return db.scalar(select(func.count()).select_from(model))


# ======================= creating applications =======================

def test_create_stores_all_fields(db):
    application = new_app(
        db,
        company="Globex",
        title="Data Engineer",
        status=ApplicationStatus.APPLIED,
        job_url="https://example.com/jobs/1",
        location="Remote",
        applied_date=date(2026, 10, 1),
        notes="Referred by a friend",
    )
    assert application.id is not None
    assert application.company == "Globex"
    assert application.job_title == "Data Engineer"
    assert application.status == "applied"
    assert application.job_url == "https://example.com/jobs/1"
    assert application.location == "Remote"
    assert application.applied_date == date(2026, 10, 1)
    assert application.notes == "Referred by a friend"
    assert application.created_at == application.updated_at


def test_status_defaults_to_wishlist(db):
    assert new_app(db).status == "wishlist"


def test_create_records_the_initial_history_entry(db):
    application = new_app(db, status=ApplicationStatus.APPLIED)
    assert len(application.status_history) == 1
    first = application.status_history[0]
    assert first.from_status is None
    assert first.to_status == "applied"


def test_create_trims_whitespace(db):
    assert new_app(db, company="  Acme  ").company == "Acme"


def test_get_returns_the_application(db):
    created = new_app(db)
    assert service.get_application(db, created.id).company == "Acme"


def test_get_unknown_id_raises(db):
    with pytest.raises(ApplicationNotFoundError, match="999"):
        service.get_application(db, 999)


# ======================= updating applications =======================

def test_update_changes_only_the_fields_that_were_sent(db):
    application = new_app(db, location="Remote", notes="keep me")
    service.update_application(db, application.id, ApplicationUpdate(company="Globex"))
    db.expire_all()
    reloaded = service.get_application(db, application.id)
    assert reloaded.company == "Globex"
    assert reloaded.location == "Remote"
    assert reloaded.notes == "keep me"


def test_update_can_clear_an_optional_field_with_null(db):
    application = new_app(db, location="Remote")
    service.update_application(db, application.id, ApplicationUpdate(location=None))
    assert service.get_application(db, application.id).location is None


def test_update_cannot_null_a_required_field():
    with pytest.raises(ValidationError):
        ApplicationUpdate(company=None)


def test_update_cannot_change_status():
    with pytest.raises(ValidationError):
        ApplicationUpdate(status="applied")


def test_update_bumps_updated_at(db):
    application = new_app(db)
    before = application.updated_at
    tick()
    service.update_application(db, application.id, ApplicationUpdate(notes="new note"))
    assert application.updated_at > before


def test_empty_update_changes_nothing(db):
    application = new_app(db)
    before = application.updated_at
    tick()
    service.update_application(db, application.id, ApplicationUpdate())
    assert application.updated_at == before


def test_update_does_not_touch_history(db):
    application = new_app(db)
    service.update_application(db, application.id, ApplicationUpdate(company="Globex"))
    assert len(application.status_history) == 1


def test_update_unknown_id_raises(db):
    with pytest.raises(ApplicationNotFoundError):
        service.update_application(db, 999, ApplicationUpdate(company="X"))


# ======================= status changes =======================

def test_status_change_updates_status_and_records_history(db):
    application = new_app(db)
    move(db, application, ApplicationStatus.APPLIED, note="Applied via the company site")

    db.expire_all()
    reloaded = service.get_application(db, application.id)
    assert reloaded.status == "applied"
    assert len(reloaded.status_history) == 2
    latest = reloaded.status_history[-1]
    assert (latest.from_status, latest.to_status) == ("wishlist", "applied")
    assert latest.note == "Applied via the company site"


def test_a_full_pipeline_is_recorded_in_order(db):
    application = new_app(db)
    for status in [ApplicationStatus.APPLIED, ApplicationStatus.INTERVIEWING, ApplicationStatus.OFFER]:
        move(db, application, status)

    db.expire_all()
    history = service.get_application(db, application.id).status_history
    assert [h.from_status for h in history] == [None, "wishlist", "applied", "interviewing"]
    assert [h.to_status for h in history] == ["wishlist", "applied", "interviewing", "offer"]


def test_moving_to_the_same_status_does_nothing(db):
    application = new_app(db)
    before = application.updated_at
    tick()
    move(db, application, ApplicationStatus.WISHLIST)
    assert len(application.status_history) == 1
    assert application.updated_at == before


def test_a_rejected_application_can_be_reopened(db):
    application = new_app(db, status=ApplicationStatus.REJECTED)
    move(db, application, ApplicationStatus.INTERVIEWING, note="They reached out again")
    assert application.status == "interviewing"
    assert application.status_history[-1].from_status == "rejected"


def test_status_change_bumps_updated_at(db):
    application = new_app(db)
    before = application.updated_at
    tick()
    move(db, application, ApplicationStatus.APPLIED)
    assert application.updated_at > before


def test_status_change_on_unknown_application_raises(db):
    with pytest.raises(ApplicationNotFoundError):
        service.change_status(db, 999, StatusChangeCreate(status=ApplicationStatus.APPLIED))


def test_status_must_be_a_known_value():
    with pytest.raises(ValidationError):
        StatusChangeCreate(status="ghosted")


# ======================= listing, filtering, searching =======================

def test_list_filters_by_status(db):
    new_app(db, "Wish Co")
    new_app(db, "Applied One", status=ApplicationStatus.APPLIED)
    new_app(db, "Applied Two", status=ApplicationStatus.APPLIED)
    found = service.list_applications(db, status=ApplicationStatus.APPLIED)
    assert sorted(a.company for a in found) == ["Applied One", "Applied Two"]


def test_search_matches_company_case_insensitively(db):
    new_app(db, "Acme Corp")
    new_app(db, "Globex")
    assert [a.company for a in service.list_applications(db, search="acme")] == ["Acme Corp"]


def test_search_matches_job_title(db):
    new_app(db, "A", "Data Scientist")
    new_app(db, "B", "Backend Engineer")
    assert [a.company for a in service.list_applications(db, search="scientist")] == ["A"]


def test_search_with_no_match_returns_empty_list(db):
    new_app(db)
    assert service.list_applications(db, search="zzz") == []


def test_percent_sign_in_search_is_literal_not_a_wildcard(db):
    new_app(db, "100% Remote Co")
    new_app(db, "Plain Co")
    assert [a.company for a in service.list_applications(db, search="%")] == ["100% Remote Co"]


def test_underscore_in_search_is_literal_not_a_wildcard(db):
    new_app(db, "snake_case Inc")
    new_app(db, "snakeXcase Inc")
    assert [a.company for a in service.list_applications(db, search="snake_case")] == ["snake_case Inc"]


def test_status_filter_and_search_combine(db):
    new_app(db, "Acme", status=ApplicationStatus.APPLIED)
    new_app(db, "Acme Labs")
    found = service.list_applications(db, status=ApplicationStatus.APPLIED, search="acme")
    assert [a.company for a in found] == ["Acme"]


def test_most_recently_updated_comes_first(db):
    first, second, third = new_app(db, "First"), new_app(db, "Second"), new_app(db, "Third")
    assert [a.company for a in service.list_applications(db)] == ["Third", "Second", "First"]

    tick()
    move(db, first, ApplicationStatus.APPLIED)
    assert [a.company for a in service.list_applications(db)][0] == "First"


def test_limit_and_offset(db):
    for number in range(5):
        new_app(db, f"Company {number}")
    assert len(service.list_applications(db, limit=2)) == 2
    assert len(service.list_applications(db, limit=10, offset=4)) == 1
    assert service.list_applications(db, limit=10, offset=5) == []


# ======================= match snapshots =======================

def test_attach_match_stores_the_snapshot(db):
    application = new_app(db)
    snapshot = service.attach_match(db, application.id, snapshot_data(score=72))

    db.expire_all()
    stored = db.scalar(select(MatchSnapshot))
    assert stored.application_id == application.id
    assert stored.score == 72
    assert stored.job_description.startswith("We need a backend engineer")
    assert stored.matched_skills == [{"skill": "Python", "category": "required"}]
    assert stored.missing_skills == [{"skill": "Docker", "category": "preferred"}]
    assert stored.attached_at.tzinfo == timezone.utc
    assert snapshot.id == stored.id


def test_attaching_again_replaces_the_snapshot(db):
    application = new_app(db)
    service.attach_match(db, application.id, snapshot_data(score=40))
    service.attach_match(db, application.id, snapshot_data(score=90, job_description="A different job."))

    db.expire_all()
    assert count(db, MatchSnapshot) == 1  # replaced, not duplicated
    stored = db.scalar(select(MatchSnapshot))
    assert stored.score == 90
    assert stored.job_description == "A different job."


def test_attaching_a_match_bumps_updated_at(db):
    application = new_app(db)
    before = application.updated_at
    tick()
    service.attach_match(db, application.id, snapshot_data())
    assert application.updated_at > before


def test_attach_to_unknown_application_raises(db):
    with pytest.raises(ApplicationNotFoundError):
        service.attach_match(db, 999, snapshot_data())


def test_remove_match_deletes_the_row(db):
    application = new_app(db)
    service.attach_match(db, application.id, snapshot_data())
    service.remove_match(db, application.id)
    db.expire_all()
    assert count(db, MatchSnapshot) == 0
    assert service.get_application(db, application.id).match_snapshot is None


def test_remove_match_when_none_attached_raises(db):
    application = new_app(db)
    with pytest.raises(MatchSnapshotNotFoundError):
        service.remove_match(db, application.id)


def test_snapshot_schema_has_no_resume_field():
    assert set(MatchSnapshotCreate.model_fields) == {
        "job_description",
        "score",
        "matched_skills",
        "missing_skills",
    }


def test_snapshot_rejects_a_resume_field():
    with pytest.raises(ValidationError) as exc_info:
        MatchSnapshotCreate(
            job_description="text",
            score=50,
            matched_skills=[],
            missing_skills=[],
            resume={"full_name": "Jane Doe"},
        )
    assert exc_info.value.errors()[0]["type"] == "extra_forbidden"


@pytest.mark.parametrize("bad_score", [-1, 101])
def test_snapshot_score_must_be_0_to_100(bad_score):
    with pytest.raises(ValidationError):
        snapshot_data(score=bad_score)


def test_snapshot_category_must_be_required_or_preferred():
    with pytest.raises(ValidationError):
        snapshot_data(matched_skills=[{"skill": "Python", "category": "optional"}])


def test_a_phase_3_match_result_converts_to_a_snapshot_and_can_be_attached(db):
    match = MatchResult(
        score=47,
        required=SkillGroupResult(
            matched=[
                SkillMatch(skill="Python", found_in="skills_section"),
                SkillMatch(skill="SQL", found_in="experience_text"),
            ],
            missing=["REST APIs"],
        ),
        preferred=SkillGroupResult(matched=[], missing=["Docker", "AWS"]),
        job=JobAnalysis(
            job_title="Backend Engineer",
            required_skills=["Python", "SQL", "REST APIs"],
            preferred_skills=["Docker", "AWS"],
            responsibilities=[],
        ),
        suggestions=["Learn Docker."],
    )
    snapshot = service.snapshot_from_match_result("The full job posting text goes here.", match)

    assert snapshot.score == 47
    assert [(e.skill, e.category) for e in snapshot.matched_skills] == [
        ("Python", "required"),
        ("SQL", "required"),
    ]
    assert [(e.skill, e.category) for e in snapshot.missing_skills] == [
        ("REST APIs", "required"),
        ("Docker", "preferred"),
        ("AWS", "preferred"),
    ]
    assert "suggestions" not in snapshot.model_dump()  # advice text is not stored

    application = new_app(db)
    service.attach_match(db, application.id, snapshot)
    assert count(db, MatchSnapshot) == 1


# ======================= deleting =======================

def test_delete_removes_the_application_and_its_children(db):
    application = new_app(db)
    move(db, application, ApplicationStatus.APPLIED)
    service.attach_match(db, application.id, snapshot_data())
    assert count(db, StatusChange) == 2

    service.delete_application(db, application.id)

    assert service.list_applications(db) == []
    assert count(db, StatusChange) == 0
    assert count(db, MatchSnapshot) == 0
    with pytest.raises(ApplicationNotFoundError):
        service.get_application(db, application.id)


def test_delete_unknown_id_raises(db):
    with pytest.raises(ApplicationNotFoundError):
        service.delete_application(db, 999)


# ======================= persistence =======================

def file_engine(tmp_path):
    return create_db_engine(f"sqlite:///{(tmp_path / 'tracker.db').as_posix()}")


def test_data_survives_closing_and_reopening_the_database_file(tmp_path):
    # --- first "server run": write data, then shut everything down ---
    engine_one = file_engine(tmp_path)
    Base.metadata.create_all(engine_one)
    session = make_session_factory(engine_one)()
    application = new_app(session, "Persisted Co", "Platform Engineer")
    move(session, application, ApplicationStatus.INTERVIEWING, note="Phone screen booked")
    service.attach_match(session, application.id, snapshot_data(score=88))
    application_id = application.id
    session.close()
    engine_one.dispose()

    assert (tmp_path / "tracker.db").exists()

    # --- second "server run": brand-new engine on the same file ---
    engine_two = file_engine(tmp_path)
    Base.metadata.create_all(engine_two)  # runs on every startup; must NOT wipe existing data
    session = make_session_factory(engine_two)()

    reloaded = service.get_application(session, application_id)
    assert reloaded.company == "Persisted Co"
    assert reloaded.status == "interviewing"
    assert [h.to_status for h in reloaded.status_history] == ["wishlist", "interviewing"]
    assert reloaded.status_history[-1].note == "Phone screen booked"
    assert reloaded.match_snapshot.score == 88
    assert reloaded.match_snapshot.missing_skills == [{"skill": "Docker", "category": "preferred"}]
    assert reloaded.created_at.tzinfo == timezone.utc

    session.close()
    engine_two.dispose()


def test_changes_that_were_never_committed_are_not_saved(tmp_path):
    engine = file_engine(tmp_path)
    Base.metadata.create_all(engine)
    factory = make_session_factory(engine)

    session = factory()
    application = new_app(session, "Committed Co")
    application_id = application.id  # save it now: after rollback/close the object cannot be read
    application.company = "Edited But Not Committed"
    session.rollback()  # undo the edit
    session.close()

    session = factory()
    assert service.get_application(session, application_id).company == "Committed Co"
    session.close()
    engine.dispose()


def test_a_second_session_sees_committed_data(db, session_factory):
    application = new_app(db, "Shared Co")
    other_session = session_factory()
    assert service.get_application(other_session, application.id).company == "Shared Co"
    other_session.close()
