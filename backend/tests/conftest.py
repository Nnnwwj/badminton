from datetime import datetime, timezone

import pytest
from fastapi.testclient import TestClient


SEEDED_NOW = datetime(2026, 10, 28, 8, 0, tzinfo=timezone.utc)


@pytest.fixture
def engine(tmp_path):
    from app.database import Base, create_db_engine

    test_engine = create_db_engine(f"sqlite:///{tmp_path / 'test.db'}")
    Base.metadata.create_all(test_engine)
    yield test_engine
    test_engine.dispose()


@pytest.fixture
def seeded_db(engine):
    from app.seed import seed_database

    seed_database(engine, now=SEEDED_NOW)
    return engine


@pytest.fixture
def client(engine):
    from app.database import create_session_factory
    from app.dependencies import get_db, get_now
    from app.main import app

    TestingSession = create_session_factory(engine)

    def override_get_db():
        with TestingSession() as db:
            yield db

    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_now] = lambda: SEEDED_NOW
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.pop(get_db, None)
    app.dependency_overrides.pop(get_now, None)
