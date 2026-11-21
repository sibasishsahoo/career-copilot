"""All tracker logic: create, read, update, delete, status changes, match snapshots.

Services receive a database Session and plain Pydantic input objects. They know nothing
about HTTP: they raise Python exceptions, and main.py turns those into status codes.
"""

from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from app.db.types import utcnow
from app.models.application import Application, ApplicationStatus, MatchSnapshot, StatusChange
from app.schemas.application import (
    ApplicationCreate,
    ApplicationUpdate,
    MatchSnapshotCreate,
    SkillEntry,
    StatusChangeCreate,
)
from app.schemas.job import MatchResult


class TrackerNotFoundError(Exception):
    """Base class: something the caller asked for does not exist (HTTP 404)."""


class ApplicationNotFoundError(TrackerNotFoundError):
    pass


class MatchSnapshotNotFoundError(TrackerNotFoundError):
    pass


def _get_or_404(db: Session, application_id: int) -> Application:
    application = db.get(Application, application_id)
    if application is None:
        raise ApplicationNotFoundError(f"Application {application_id} was not found.")
    return application


# ---------------------------- create / read ----------------------------

def create_application(db: Session, data: ApplicationCreate) -> Application:
    now = utcnow()
    application = Application(
        company=data.company,
        job_title=data.job_title,
        status=data.status.value,
        job_url=data.job_url,
        location=data.location,
        applied_date=data.applied_date,
        notes=data.notes,
        created_at=now,
        updated_at=now,
    )
    # The history always starts with a "creation" entry (from_status is None).
    application.status_history.append(
        StatusChange(from_status=None, to_status=data.status.value, changed_at=now)
    )
    db.add(application)
    db.commit()
    return application


def get_application(db: Session, application_id: int) -> Application:
    return _get_or_404(db, application_id)


def _like_pattern(term: str) -> str:
    """Escape LIKE wildcards so a search for "100%" finds "100%" and not everything.
    (SQL injection is already prevented by bound parameters; this is a separate issue.)"""
    escaped = term.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
    return f"%{escaped}%"


def list_applications(
    db: Session,
    status: ApplicationStatus | None = None,
    search: str | None = None,
    limit: int = 50,
    offset: int = 0,
) -> list[Application]:
    statement = select(Application)

    if status is not None:
        statement = statement.where(Application.status == status.value)

    if search and search.strip():
        pattern = _like_pattern(search.strip())
        statement = statement.where(
            or_(
                Application.company.ilike(pattern, escape="\\"),
                Application.job_title.ilike(pattern, escape="\\"),
            )
        )

    # Most recently touched first; id breaks ties so the order is always deterministic.
    statement = (
        statement.order_by(Application.updated_at.desc(), Application.id.desc())
        .limit(limit)
        .offset(offset)
    )
    return list(db.scalars(statement).all())


# ---------------------------- update / delete ----------------------------

def update_application(db: Session, application_id: int, data: ApplicationUpdate) -> Application:
    application = _get_or_404(db, application_id)

    # exclude_unset=True is the heart of PATCH: it contains ONLY the fields the client
    # actually sent. Not sent = untouched. Sent as null = cleared (for optional fields).
    changes = data.model_dump(exclude_unset=True)
    for field, value in changes.items():
        setattr(application, field, value)

    if changes:
        application.updated_at = utcnow()
    db.commit()
    return application


def delete_application(db: Session, application_id: int) -> None:
    application = _get_or_404(db, application_id)
    db.delete(application)  # history and snapshot are deleted too (cascade)
    db.commit()


# ---------------------------- status changes ----------------------------

def change_status(db: Session, application_id: int, data: StatusChangeCreate) -> Application:
    """Move an application to a new status and record the change.

    Any status may follow any other (people get re-opened after a rejection, withdraw after
    an offer, and so on). Asking for the status it already has does nothing: no history row.
    """
    application = _get_or_404(db, application_id)
    new_status = data.status.value

    if application.status == new_status:
        return application

    now = utcnow()
    application.status_history.append(
        StatusChange(
            from_status=application.status,
            to_status=new_status,
            note=data.note,
            changed_at=now,
        )
    )
    application.status = new_status
    application.updated_at = now
    db.commit()
    return application


# ---------------------------- match snapshots ----------------------------

def attach_match(db: Session, application_id: int, data: MatchSnapshotCreate) -> MatchSnapshot:
    """Save (or replace) the match snapshot of an application. There is at most one."""
    application = _get_or_404(db, application_id)
    now = utcnow()

    values = {
        "job_description": data.job_description,
        "score": data.score,
        "matched_skills": [entry.model_dump() for entry in data.matched_skills],
        "missing_skills": [entry.model_dump() for entry in data.missing_skills],
        "attached_at": now,
    }

    if application.match_snapshot is None:
        application.match_snapshot = MatchSnapshot(**values)
    else:
        for field, value in values.items():
            setattr(application.match_snapshot, field, value)

    application.updated_at = now
    db.commit()
    return application.match_snapshot


def remove_match(db: Session, application_id: int) -> None:
    application = _get_or_404(db, application_id)
    if application.match_snapshot is None:
        raise MatchSnapshotNotFoundError(
            f"Application {application_id} has no match snapshot attached."
        )
    application.match_snapshot = None  # delete-orphan removes the row
    application.updated_at = utcnow()
    db.commit()


def snapshot_from_match_result(job_description: str, match: MatchResult) -> MatchSnapshotCreate:
    """Convert a Phase 3 MatchResult into a snapshot ready to attach.

    Note what is NOT copied: the suggestions, the job analysis, and of course the resume.
    """

    def entries(skills: list[str], category: str) -> list[SkillEntry]:
        return [SkillEntry(skill=skill, category=category) for skill in skills]

    return MatchSnapshotCreate(
        job_description=job_description,
        score=match.score,
        matched_skills=(
            entries([hit.skill for hit in match.required.matched], "required")
            + entries([hit.skill for hit in match.preferred.matched], "preferred")
        ),
        missing_skills=(
            entries(match.required.missing, "required")
            + entries(match.preferred.missing, "preferred")
        ),
    )
