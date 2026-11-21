import pytest
from fastapi.testclient import TestClient

from app import models as _models  # noqa: F401  (importing registers the tables on Base.metadata)
from app.config import Settings, get_settings
from app.db.base import Base
from app.db.session import create_db_engine, get_db, make_session_factory
from app.main import app


@pytest.fixture
def engine():
    """A brand-new, empty, in-memory SQLite database for each test. Nothing touches disk."""
    engine = create_db_engine("sqlite://")
    Base.metadata.create_all(engine)
    yield engine
    engine.dispose()


@pytest.fixture
def session_factory(engine):
    return make_session_factory(engine)


@pytest.fixture
def db(session_factory):
    """A database session for tests that call services or the ORM directly."""
    session = session_factory()
    yield session
    session.close()


@pytest.fixture
def client(session_factory):
    """A test client whose settings never read the real .env file or shell env,
    and whose database is the in-memory one above (never your real database file)."""
    app.dependency_overrides[get_settings] = lambda: Settings(
        _env_file=None,
        llm_provider="gemini",
        gemini_api_key="super-secret-fake-key",
    )

    def override_get_db():
        session = session_factory()
        try:
            yield session
        finally:
            session.close()

    app.dependency_overrides[get_db] = override_get_db
    yield TestClient(app)
    app.dependency_overrides.clear()
