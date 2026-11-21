"""ORM models = the database tables.

Three tables:

    applications 1 ──< status_changes      (history: one row per status change)
    applications 1 ──  match_snapshots     (at most one optional snapshot per application)

PRIVACY RULE: nothing in this file stores a resume - not the file, not its text, not
parsed fields. A match snapshot keeps only the JOB description, the score, and skill names.
"""

from datetime import date, datetime
from enum import Enum
from typing import Optional

from sqlalchemy import JSON, CheckConstraint, Date, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.db.types import UTCDateTime, utcnow


class ApplicationStatus(str, Enum):
    WISHLIST = "wishlist"
    APPLIED = "applied"
    INTERVIEWING = "interviewing"
    OFFER = "offer"
    REJECTED = "rejected"
    WITHDRAWN = "withdrawn"


# "'wishlist', 'applied', ..." - used to build database-level CHECK constraints below.
_STATUS_VALUES = ", ".join(f"'{status.value}'" for status in ApplicationStatus)


class Application(Base):
    __tablename__ = "applications"
    __table_args__ = (
        # Defense in depth: even code that bypasses our Pydantic validation cannot
        # store a status that is not in the list.
        CheckConstraint(f"status IN ({_STATUS_VALUES})", name="ck_applications_status"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    company: Mapped[str] = mapped_column(String(200))
    job_title: Mapped[str] = mapped_column(String(200))
    status: Mapped[str] = mapped_column(String(20), index=True)
    job_url: Mapped[str | None] = mapped_column(String(2000))
    location: Mapped[str | None] = mapped_column(String(200))
    applied_date: Mapped[date | None] = mapped_column(Date)
    notes: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime(), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(UTCDateTime(), default=utcnow)

    # cascade="all, delete-orphan": deleting an application also deletes its history and snapshot.
    status_history: Mapped[list["StatusChange"]] = relationship(
        back_populates="application",
        cascade="all, delete-orphan",
        order_by="StatusChange.id",
    )
    match_snapshot: Mapped[Optional["MatchSnapshot"]] = relationship(
        back_populates="application",
        cascade="all, delete-orphan",
        uselist=False,  # a single object (or None), not a list
    )
    interview_prep: Mapped[Optional["InterviewPrep"]] = relationship(
        back_populates="application",
        cascade="all, delete-orphan",
        uselist=False,
    )


class StatusChange(Base):
    """One row per status change. The very first row has from_status = NULL (creation)."""

    __tablename__ = "status_changes"
    __table_args__ = (
        CheckConstraint(f"to_status IN ({_STATUS_VALUES})", name="ck_status_changes_to_status"),
        CheckConstraint(
            f"from_status IS NULL OR from_status IN ({_STATUS_VALUES})",
            name="ck_status_changes_from_status",
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    application_id: Mapped[int] = mapped_column(
        ForeignKey("applications.id", ondelete="CASCADE"), index=True
    )
    from_status: Mapped[str | None] = mapped_column(String(20))
    to_status: Mapped[str] = mapped_column(String(20))
    note: Mapped[str | None] = mapped_column(Text)
    changed_at: Mapped[datetime] = mapped_column(UTCDateTime(), default=utcnow)

    application: Mapped["Application"] = relationship(back_populates="status_history")


class MatchSnapshot(Base):
    """A saved copy of a Phase 3 match result. NO resume data - see the privacy rule above."""

    __tablename__ = "match_snapshots"
    __table_args__ = (
        CheckConstraint("score >= 0 AND score <= 100", name="ck_match_snapshots_score"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    # unique=True is what makes this "at most ONE snapshot per application"
    application_id: Mapped[int] = mapped_column(
        ForeignKey("applications.id", ondelete="CASCADE"), unique=True
    )
    job_description: Mapped[str] = mapped_column(Text)
    score: Mapped[int]
    # JSON columns: lists like [{"skill": "Python", "category": "required"}, ...]
    matched_skills: Mapped[list[dict]] = mapped_column(JSON)
    missing_skills: Mapped[list[dict]] = mapped_column(JSON)
    attached_at: Mapped[datetime] = mapped_column(UTCDateTime(), default=utcnow)

    application: Mapped["Application"] = relationship(back_populates="match_snapshot")
