from unittest.mock import patch

from fastapi.testclient import TestClient


def test_root_endpoint(client: TestClient) -> None:
    response = client.get("/")
    assert response.status_code == 200
    data = response.json()
    assert "service" in data
    assert "version" in data
    assert "health" in data


def test_liveness_endpoint(client: TestClient) -> None:
    response = client.get("/api/v1/health/live")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "alive"
    assert data["service"] == "foundersignal-api"
    assert "version" in data
    assert "timestamp" in data


def test_readiness_endpoint_healthy(client: TestClient) -> None:
    with patch("app.api.v1.endpoints.health.check_db_connection", return_value=True):
        response = client.get("/api/v1/health/ready")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "ready"
        assert data["database_connected"] is True
        assert data["service"] == "foundersignal-api"


def test_readiness_endpoint_unavailable(client: TestClient) -> None:
    with patch("app.api.v1.endpoints.health.check_db_connection", return_value=False):
        response = client.get("/api/v1/health/ready")
        assert response.status_code == 503
        data = response.json()
        assert data["status"] == "unavailable"
        assert data["database_connected"] is False


def test_legacy_health_endpoint_healthy(client: TestClient) -> None:
    with patch("app.api.v1.endpoints.health.check_db_connection", return_value=True):
        response = client.get("/api/v1/health")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "ready"
        assert data["database_connected"] is True


def test_legacy_health_endpoint_unavailable(client: TestClient) -> None:
    with patch("app.api.v1.endpoints.health.check_db_connection", return_value=False):
        response = client.get("/api/v1/health")
        assert response.status_code == 503
        data = response.json()
        assert data["status"] == "unavailable"
        assert data["database_connected"] is False
