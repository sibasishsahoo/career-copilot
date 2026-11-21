"""Timestamp handling.

SQLite has NO real timezone support: it stores a datetime as plain text and forgets
the timezone. If we ignored that, a datetime we saved as UTC would come back "naive"
(no timezone) and could be mixed up with local time.

Our rule: in Python we ALWAYS use timezone-aware UTC datetimes. UTCDateTime converts
them to naive UTC when saving and puts the UTC timezone back when loading.
"""

from datetime import datetime, timezone

from sqlalchemy import DateTime
from sqlalchemy.types import TypeDecorator


def utcnow() -> datetime:
    """Current time as a timezone-aware UTC datetime."""
    return datetime.now(timezone.utc)


class UTCDateTime(TypeDecorator):
    impl = DateTime
    cache_ok = True  # tells SQLAlchemy this type is safe to cache

    def process_bind_param(self, value, dialect):
        """Python -> database."""
        if value is None:
            return None
        if value.tzinfo is None:
            raise ValueError("Naive datetime given. Use timezone-aware UTC datetimes (see utcnow()).")
        return value.astimezone(timezone.utc).replace(tzinfo=None)

    def process_result_value(self, value, dialect):
        """Database -> Python."""
        if value is None:
            return None
        return value.replace(tzinfo=timezone.utc)
