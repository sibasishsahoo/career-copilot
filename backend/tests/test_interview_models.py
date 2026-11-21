"""The interview_preps table: constraints, cascades and value handling."""

from datetime import timezone

import pytest
from sqlalchemy import delete, func, select
from sqlalchemy.exc import IntegrityError

from app.db.base import Base
from app.db.types import utcnow
from app.models.application import Application
from app.models.interview_prep import InterviewPrep

CONTENT = {
    "items": [{"number": 1, "question": "Tell me about X?", "story_found": True, "sources": ["Note A"]}],
    "questions_to_ask": ["What does success look like?"],
    "coverage": {"total": 1, "with_story": 1, "without_story": []},
}


def add_application(db) -> Application:
    now = utcnow()
    application = Application(company="Acme", job_title="Engineer", status="wishlist", created_at=now, updated_at=now)
    db.add(application)
    db.commit()
    return application


def add_prep(db, application, content=None) -> InterviewPrep:
    prep = InterviewPrep(application_id=application.id, content=content or CONTENT, generated_at=utcnow())
    db.add(prep)
    db.commit()
    return prep


def count(db) -> int:
    return db.scalar(select(func.count()).select_from(InterviewPrep))


def test_the_table_has_exactly_the_expected_columns_and_no_place_for_a_resume():
    columns = {column.name for column in Base.metadata.tables["interview_preps"].columns}
    assert columns == {"id", "application_id", "content", "generated_at"}


def test_only_one_prep_per_application(db):
    application = add_application(db)
    add_prep(db, application)
    db.add(InterviewPrep(application_id=application.id, content=CONTENT))
    with pytest.raises(IntegrityError):
        db.commit()
    db.rollback()


def test_a_prep_needs_an_existing_application(db):
    db.add(InterviewPrep(application_id=999, content=CONTENT))
    with pytest.raises(IntegrityError):
        db.commit()
    db.rollback()


def test_content_round_trips_and_the_timestamp_is_utc(db):
    application = add_application(db)
    prep = add_prep(db, application)
    db.expire_all()
    reloaded = db.get(InterviewPrep, prep.id)
    assert reloaded.content == CONTENT
    assert reloaded.generated_at.tzinfo == timezone.utc


def test_deleting_an_application_through_the_orm_deletes_its_prep(db):
    application = add_application(db)
    add_prep(db, application)
    db.delete(application)
    db.commit()
    assert count(db) == 0


def test_the_database_itself_deletes_a_prep_with_its_application(db):
    """A bulk DELETE skips the ORM, so only the database's ON DELETE CASCADE can remove the prep."""
    application = add_application(db)
    add_prep(db, application)
    db.execute(delete(Application).where(Application.id == application.id))
    db.commit()
    assert count(db) == 0


def test_the_application_can_reach_its_prep_and_back(db):
    application = add_application(db)
    prep = add_prep(db, application)
    db.expire_all()
    assert db.get(Application, application.id).interview_prep.id == prep.id
    assert db.get(InterviewPrep, prep.id).application.company == "Acme"
