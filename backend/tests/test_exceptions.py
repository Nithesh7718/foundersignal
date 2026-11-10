from fastapi.testclient import TestClient

from app.core.exceptions import AppException
from app.main import app


def test_structured_app_exception_format() -> None:
    @app.get("/api/v1/test-app-error")
    def trigger_error() -> None:
        raise AppException(
            status_code=400,
            code="INVALID_COMMITMENT_STATE",
            message="Cannot approve already rejected commitment.",
            details={"commitment_id": 42},
        )

    with TestClient(app) as client:
        response = client.get("/api/v1/test-app-error")
        assert response.status_code == 400
        data = response.json()
        assert "error" in data
        assert data["error"]["code"] == "INVALID_COMMITMENT_STATE"
        assert data["error"]["details"]["commitment_id"] == 42


def test_unhandled_exception_sanitisation() -> None:
    sensitive_db_url = "postgresql://user:SUPER_SECRET_PASSWORD@db-host:5432/production_db"

    @app.get("/api/v1/test-unhandled-error")
    def trigger_unhandled() -> None:
        # Simulate a database exception containing sensitive connection credentials
        raise RuntimeError(f"Connection failure to {sensitive_db_url} at /var/secrets/key.pem")

    with TestClient(app, raise_server_exceptions=False) as client:
        response = client.get("/api/v1/test-unhandled-error")
        assert response.status_code == 500
        data = response.json()
        raw_text = response.text

        # Verify sensitive credentials and paths are never leaked to client
        assert "SUPER_SECRET_PASSWORD" not in raw_text
        assert "db-host" not in raw_text
        assert "/var/secrets" not in raw_text

        # Verify structured error code is returned
        assert data["error"]["code"] == "INTERNAL_SERVER_ERROR"
        assert "unexpected error occurred" in data["error"]["message"].lower()
