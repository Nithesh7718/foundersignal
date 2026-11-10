from unittest.mock import patch

from fastapi.testclient import TestClient


def test_root_endpoint(client: TestClient) -> None:
    response = client.get("/")
    assert response.status_code == 200
    data = response.json()
    assert "service" in data
    assert "version" in data
    assert "health" in data


def test_health_endpoint_healthy(client: TestClient) -> None:
    with patch("app.api.v1.endpoints.health.check_db_connection", return_value=True):
        response = client.get("/api/v1/health")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "healthy"
        assert data["service"] == "foundersignal-api"
        assert data["database_connected"] is True
        assert "timestamp" in data


def test_health_endpoint_degraded_when_db_down(client: TestClient) -> None:
    with patch("app.api.v1.endpoints.health.check_db_connection", return_value=False):
        response = client.get("/api/v1/health")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "degraded"
        assert data["database_connected"] is False
