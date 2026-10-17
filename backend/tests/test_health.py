from collections.abc import Iterator
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from app.main import app


@pytest.fixture
def client() -> Iterator[TestClient]:
    with patch("app.main.create_db_engine"), TestClient(app) as test_client:
        yield test_client


def test_live_healthcheck(client: TestClient) -> None:
    response = client.get("/health/live")

    assert response.status_code == 200
    assert response.json() == {"status": "ok", "service": "api"}


def test_ready_healthcheck(client: TestClient) -> None:
    with patch("app.main.database_is_ready", return_value=True):
        response = client.get("/health/ready")

    assert response.status_code == 200
    assert response.json() == {"status": "ready", "service": "api"}
