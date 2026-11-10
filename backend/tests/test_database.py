from unittest.mock import MagicMock, patch

import pytest

from app.core.database import check_db_connection, get_db


def test_get_db_session_lifecycle() -> None:
    gen = get_db()
    session = next(gen)
    assert session is not None
    # Closing the generator should close the session cleanly
    try:
        next(gen)
    except StopIteration:
        pass


def test_get_db_rollback_on_transaction_failure() -> None:
    mock_session = MagicMock()

    with patch("app.core.database.SessionLocal", return_value=mock_session):
        gen = get_db()
        session = next(gen)
        assert session == mock_session

        # Simulate unhandled error in request handling
        test_error = RuntimeError("Database query crashed")
        with pytest.raises(RuntimeError, match="Database query crashed"):
            gen.throw(test_error)

        # Verify rollback was called before propagating the exception
        mock_session.rollback.assert_called_once()
        mock_session.close.assert_called_once()


def test_check_db_connection_handles_failure() -> None:
    with patch("app.core.database.engine.connect", side_effect=Exception("Connection refused")):
        result = check_db_connection()
        assert result is False
