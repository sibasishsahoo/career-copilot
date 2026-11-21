"""The latest interview-prep pack of an application.

At most ONE row per application (unique application_id); generating again replaces it.

PRIVACY: a pack is built only from the job description (saved with the match) and the user's own
notes. The resume is never used, so it can never end up in this table.
"""

from datetime import datetime

from sqlalchemy import JSON, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.db.types import UTCDateTime, utcnow


class InterviewPrep(Base):
    __tablename__ = "interview_preps"

    id: Mapped[int] = mapped_column(primary_key=True)
    application_id: Mapped[int] = mapped_column(
        ForeignKey("applications.id", ondelete="CASCADE"), unique=True
    )
    # {"items": [...], "questions_to_ask": [...], "coverage": {...}} - validated when it is written and read
    content: Mapped[dict] = mapped_column(JSON)
    generated_at: Mapped[datetime] = mapped_column(UTCDateTime(), default=utcnow)

    application: Mapped["Application"] = relationship(back_populates="interview_prep")
