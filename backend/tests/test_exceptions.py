from fastapi.testclient import TestClient

from app.core.exceptions import AppException
from app.main import app


def test_structured_app_exception_format() -> None:
    # Register temporary test route to trigger AppException
    @app.get("/api/v1/test-error")
    def trigger_error() -> None:
        raise AppException(
            status_code=400,
            code="INVALID_COMMITMENT_STATE",
            message="Cannot approve already rejected commitment.",
            details={"commitment_id": 42},
        )

    with TestClient(app) as client:
        response = client.get("/api/v1/test-error")
        assert response.status_code == 400
        data = response.json()
        assert "error" in data
        assert data["error"]["code"] == "INVALID_COMMITMENT_STATE"
        assert data["error"]["details"]["commitment_id"] == 42
