import pytest
from app.main import app
from fastapi.testclient import TestClient


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setenv("DB_PATH", str(tmp_path / "test.db"))
    monkeypatch.setenv("KAFKA_ENABLED", "false")
    monkeypatch.setenv("RABBITMQ_ENABLED", "false")
    with TestClient(app) as test_client:
        yield test_client
