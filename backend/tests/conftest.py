import pytest
from fastapi.testclient import TestClient


@pytest.fixture
def engine(tmp_path):
    from app.database import Base, create_db_engine

    test_engine = create_db_engine(f"sqlite:///{tmp_path / 'test.db'}")
    Base.metadata.create_all(test_engine)
    yield test_engine
    test_engine.dispose()


@pytest.fixture
def client():
    from app.main import app

    with TestClient(app) as test_client:
        yield test_client
