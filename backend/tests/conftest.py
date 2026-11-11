from collections.abc import Generator

import pytest
from fastapi.testclient import TestClient

from app.core.config import settings
from app.main import app


@pytest.fixture(autouse=True)
def mock_providers_for_tests(monkeypatch: pytest.MonkeyPatch) -> Generator[None, None, None]:
    """Ensure automated tests run with MOCK_PROVIDERS=True by default."""
    monkeypatch.setattr(settings, "MOCK_PROVIDERS", True)
    yield


@pytest.fixture(scope="session")
def client() -> TestClient:
    """Synchronous test client fixture for FastAPI application."""
    with TestClient(app) as test_client:
        yield test_client
