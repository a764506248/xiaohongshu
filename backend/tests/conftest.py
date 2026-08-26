import os

os.environ["DATABASE_URL"] = "sqlite:///./xiaohongshu-test.db"
os.environ["CHECKPOINT_DATABASE_URL"] = ""
os.environ["LLM_PROVIDER"] = "mock"
os.environ["APP_ENV"] = "test"

import pytest
from fastapi.testclient import TestClient

from app.core.database import Base, engine
from app.main import app


@pytest.fixture()
def client():
    Base.metadata.drop_all(engine)
    Base.metadata.create_all(engine)
    with TestClient(app) as test_client:
        yield test_client
