"""Engine, sessions and database initialization.

Vocabulary:
  Engine   = the connection to the database (one per application).
  Session  = one "conversation" with the database: you load objects, change them,
             then commit (save) or roll back (undo). We use ONE session PER REQUEST.
"""

from collections.abc import Iterator
from functools import lru_cache

from sqlalchemy import create_engine, event
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.config import get_settings
from app.db.base import Base


def create_db_engine(database_url: str) -> Engine:
    """Build an engine. Used by the app AND by the tests (with an in-memory database)."""
    options: dict = {}
    is_sqlite = database_url.startswith("sqlite")

    if is_sqlite:
        # FastAPI runs our `def` routes in worker threads; SQLite normally refuses to be
        # used from a thread other than the one that opened it. Each request gets its own
        # session, so sharing the connection settings like this is safe here.
        options["connect_args"] = {"check_same_thread": False}
        if database_url in ("sqlite://", "sqlite:///:memory:"):
            # An in-memory database lives inside ONE connection. StaticPool makes every
            # session reuse that single connection, so they all see the same database.
            options["poolclass"] = StaticPool

    engine = create_engine(database_url, **options)

    if is_sqlite:

        @event.listens_for(engine, "connect")
        def enable_foreign_keys(dbapi_connection, connection_record):
            # SQLite ignores FOREIGN KEY rules unless you switch them on per connection.
            cursor = dbapi_connection.cursor()
            cursor.execute("PRAGMA foreign_keys=ON")
            cursor.close()

    return engine


def make_session_factory(engine: Engine) -> sessionmaker[Session]:
    # autoflush=False : changes are sent to the database only when WE commit - easier to reason about.
    # expire_on_commit=False : after commit(), objects keep their values instead of being re-loaded.
    return sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)


@lru_cache
def get_engine() -> Engine:
    return create_db_engine(get_settings().database_url)


@lru_cache
def get_session_factory() -> sessionmaker[Session]:
    return make_session_factory(get_engine())


def get_db() -> Iterator[Session]:
    """FastAPI dependency: one session per request, always closed afterwards.

    Everything before `yield` runs when the request starts, everything after when it ends.
    """
    session = get_session_factory()()
    try:
        yield session
    except Exception:
        session.rollback()  # something failed: undo any half-finished changes
        raise
    finally:
        session.close()


def init_db() -> None:
    """Create all tables that do not exist yet. Safe to run on every startup:
    existing tables (and their data) are left untouched."""
    import app.models  # noqa: F401  (importing registers the tables on Base.metadata)

    Base.metadata.create_all(bind=get_engine())
