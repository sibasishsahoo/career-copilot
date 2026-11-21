"""Pydantic schemas for the application tracker = the SHAPE OF THE API.

These are deliberately separate from the ORM models (the shape of the database):
  * the API never exposes columns we don't want to expose,
  * the database can change without breaking the API (and vice versa),
  * input rules (what a client may SEND) differ from output rules (what we RETURN).

Input schemas use extra="forbid": unknown fields are rejected with a 422 instead of being
silently ignored. This also guards privacy - e.g. a client that tries to send a "resume"
field along with a match snapshot gets an error instead of the field being dropped quietly.
"""

from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.models.application import ApplicationStatus
from app.schemas.job import MAX_JOB_CHARS

__all__ = [
    "ApplicationCreate",
    "ApplicationDetail",
    "ApplicationRead",
    "ApplicationStatus",
    "ApplicationUpdate",
    "MatchSnapshotCreate",
    "MatchSnapshotRead",
    "SkillEntry",
    "StatusChangeCreate",
    "StatusChangeRead",
]


def _check_http_url(value: str | None) -> str | None:
    # Only http(s) links are allowed. A "javascript:..." link stored here could become an
    # XSS hole when a frontend later renders it as a clickable link.
    if value is not None and not value.lower().startswith(("http://", "https://")):
        raise ValueError("must start with http:// or https://")
    return value


# ======================= input (what clients send) =======================

class ApplicationCreate(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")

    company: str = Field(min_length=1, max_length=200)
    job_title: str = Field(min_length=1, max_length=200)
    status: ApplicationStatus = ApplicationStatus.WISHLIST
    job_url: str | None = Field(default=None, max_length=2000)
    location: str | None = Field(default=None, max_length=200)
    applied_date: date | None = None
    notes: str | None = Field(default=None, max_length=5000)

    @field_validator("job_url")
    @classmethod
    def validate_url(cls, value: str | None) -> str | None:
        return _check_http_url(value)


class ApplicationUpdate(BaseModel):
    """Body of PATCH. Every field is optional: only the fields you send are changed.

    Status is deliberately NOT here. Status changes go through their own endpoint so that
    every change is recorded in the history. Sending "status" here returns a 422.
    """

    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")

    company: str | None = Field(default=None, min_length=1, max_length=200)
    job_title: str | None = Field(default=None, min_length=1, max_length=200)
    job_url: str | None = Field(default=None, max_length=2000)
    location: str | None = Field(default=None, max_length=200)
    applied_date: date | None = None
    notes: str | None = Field(default=None, max_length=5000)

    @field_validator("company", "job_title")
    @classmethod
    def required_columns_cannot_be_cleared(cls, value: str | None) -> str | None:
        # "Field not sent" is fine (validators don't run for defaults), but an explicit
        # null would try to erase a required column, so we refuse it.
        if value is None:
            raise ValueError("cannot be null")
        return value

    @field_validator("job_url")
    @classmethod
    def validate_url(cls, value: str | None) -> str | None:
        return _check_http_url(value)


class StatusChangeCreate(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")

    status: ApplicationStatus
    note: str | None = Field(default=None, max_length=1000)


class SkillEntry(BaseModel):
    skill: str = Field(min_length=1, max_length=100)
    category: Literal["required", "preferred"]


class MatchSnapshotCreate(BaseModel):
    """The fields of a Phase 3 match worth keeping. There is intentionally NO resume field."""

    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")

    job_description: str = Field(min_length=1, max_length=MAX_JOB_CHARS)
    score: int = Field(ge=0, le=100)
    matched_skills: list[SkillEntry] = Field(max_length=200)
    missing_skills: list[SkillEntry] = Field(max_length=200)


# ======================= output (what we return) =======================
# from_attributes=True lets Pydantic read values straight from ORM objects.

class StatusChangeRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    from_status: ApplicationStatus | None
    to_status: ApplicationStatus
    note: str | None
    changed_at: datetime


class MatchSnapshotRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    job_description: str
    score: int
    matched_skills: list[SkillEntry]
    missing_skills: list[SkillEntry]
    attached_at: datetime


class ApplicationRead(BaseModel):
    """Summary used in lists."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    company: str
    job_title: str
    status: ApplicationStatus
    job_url: str | None
    location: str | None
    applied_date: date | None
    notes: str | None
    created_at: datetime
    updated_at: datetime


class ApplicationDetail(ApplicationRead):
    """Full view of one application: summary + history + optional match snapshot."""

    status_history: list[StatusChangeRead]
    match_snapshot: MatchSnapshotRead | None
