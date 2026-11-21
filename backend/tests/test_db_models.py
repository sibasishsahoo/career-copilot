"""Tests of the database itself: tables, constraints, cascades, timestamps.

These bypass our services on purpose, to prove the DATABASE enforces its own rules even
when application code is buggy or skips validation.
"""

from datetime import datetime, timezone

import pytest
from sqlalchemy import delete, func, inspect, select, text
from sqlalchemy.exc import IntegrityError, StatementError

from app.db.base import Base
from app.db.types import utcnow
from app.models.application import Application, MatchSnapshot, StatusChange


def add_application(db, **overrides) -> Application:
    now = utcnow()
    values = dict(company="Acme", job_title="Engineer", status="wishlist", created_at=now, updated_at=now)
    values.update(overrides)
    application = Application(**values)
    db.add(application)
    db.commit()
    return application


def count(db, model) -> int:
    return db.scalar(select(func.count()).select_from(model))


# ---------- structure ----------

def test_expected_tables_exist(engine):
    assert set(inspect(engine).get_table_names()) == {
        "applications", "status_changes", "match_snapshots", "interview_preps",
    }


def test_match_snapshot_has_exactly_the_agreed_columns():
    columns = {column.name for column in Base.metadata.tables["match_snapshots"].columns}
    assert columns == {
        "id",
        "application_id",
        "job_description",
        "score",
        "matched_skills",
        "missing_skills",
        "attached_at",
    }


def test_no_table_or_column_can_hold_resume_data():
    """Privacy guard: if someone adds a resume-like column, this test fails."""
    for table in Base.metadata.tables.values():
        assert "resume" not in table.name
        for column in table.columns:
            assert "resume" not in column.name
            assert "cv" not in column.name.split("_")


# ---------- constraints enforced by the database ----------

def test_foreign_keys_are_switched_on(db):
    assert db.execute(text("PRAGMA foreign_keys")).scalar() == 1


def test_invalid_application_status_is_rejected(db):
    now = utcnow()
    db.add(Application(company="A", job_title="B", status="bogus", created_at=now, updated_at=now))
    with pytest.raises(IntegrityError):
        db.commit()
    db.rollback()


def test_invalid_history_status_is_rejected(db):
    application = add_application(db)
    db.add(StatusChange(application_id=application.id, from_status=None, to_status="bogus"))
    with pytest.raises(IntegrityError):
        db.commit()
    db.rollback()


def test_history_row_needs_an_existing_application(db):
    db.add(StatusChange(application_id=999, from_status=None, to_status="applied"))
    with pytest.raises(IntegrityError):
        db.commit()
    db.rollback()


@pytest.mark.parametrize("bad_score", [-1, 101, 1000])
def test_score_outside_0_to_100_is_rejected(db, bad_score):
    application = add_application(db)
    db.add(
        MatchSnapshot(
            application_id=application.id,
            job_description="text",
            score=bad_score,
            matched_skills=[],
            missing_skills=[],
        )
    )
    with pytest.raises(IntegrityError):
        db.commit()
    db.rollback()


def test_only_one_snapshot_per_application(db):
    application = add_application(db)
    for _ in range(2):
        db.add(
            MatchSnapshot(
                application_id=application.id,
                job_description="text",
                score=50,
                matched_skills=[],
                missing_skills=[],
            )
        )
    with pytest.raises(IntegrityError):
        db.commit()
    db.rollback()


def test_database_deletes_children_when_a_parent_is_deleted(db):
    """A bulk DELETE skips the ORM completely, so only the database's own
    ON DELETE CASCADE rule can remove the children."""
    application = add_application(db)
    db.add(StatusChange(application_id=application.id, from_status=None, to_status="wishlist"))
    db.add(
        MatchSnapshot(
            application_id=application.id,
            job_description="text",
            score=50,
            matched_skills=[],
            missing_skills=[],
        )
    )
    db.commit()
    assert count(db, StatusChange) == 1
    assert count(db, MatchSnapshot) == 1

    db.execute(delete(Application).where(Application.id == application.id))
    db.commit()

    assert count(db, Application) == 0
    assert count(db, StatusChange) == 0
    assert count(db, MatchSnapshot) == 0


# ---------- value handling ----------

def test_timestamps_come_back_as_timezone_aware_utc(db):
    moment = utcnow()
    application = add_application(db, created_at=moment, updated_at=moment)
    db.expire_all()  # forget Python's copy so the value is really re-read from the database

    reloaded = db.get(Application, application.id)
    assert reloaded.created_at.tzinfo == timezone.utc
    assert reloaded.created_at == moment


def test_naive_datetimes_are_refused(db):
    naive = datetime(2026, 1, 1, 12, 0, 0)
    db.add(Application(company="A", job_title="B", status="wishlist", created_at=naive, updated_at=naive))
    with pytest.raises((StatementError, ValueError)):
        db.commit()
    db.rollback()


def test_json_columns_round_trip(db):
    application = add_application(db)
    matched = [{"skill": "Python", "category": "required"}]
    missing = [{"skill": "Docker", "category": "preferred"}]
    db.add(
        MatchSnapshot(
            application_id=application.id,
            job_description="text",
            score=60,
            matched_skills=matched,
            missing_skills=missing,
        )
    )
    db.commit()
    db.expire_all()

    snapshot = db.scalar(select(MatchSnapshot))
    assert snapshot.matched_skills == matched
    assert snapshot.missing_skills == missing


def test_relationships_load_children_in_order(db):
    application = add_application(db)
    for old, new in [(None, "wishlist"), ("wishlist", "applied"), ("applied", "offer")]:
        db.add(StatusChange(application_id=application.id, from_status=old, to_status=new))
    db.commit()
    db.expire_all()

    reloaded = db.get(Application, application.id)
    assert [change.to_status for change in reloaded.status_history] == ["wishlist", "applied", "offer"]
