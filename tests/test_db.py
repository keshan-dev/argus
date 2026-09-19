"""Unit tests for database session management (P1-004, Issue #10)."""

from unittest.mock import MagicMock

import pytest
from sqlalchemy.exc import OperationalError

from app.db import get_session, get_sync_session, is_timeout_error


def test_is_timeout_error_detection() -> None:
    """is_timeout_error accurately identifies PostgreSQL statement cancellation."""
    timeout_err = OperationalError(
        statement="SELECT 1",
        params={},
        orig=Exception("canceling statement due to statement timeout"),
    )
    assert is_timeout_error(timeout_err) is True

    generic_err = OperationalError(
        statement="SELECT 1",
        params={},
        orig=Exception("relation does not exist"),
    )
    assert is_timeout_error(generic_err) is False

    value_err = ValueError("Something else")
    assert is_timeout_error(value_err) is False


def test_get_session_lifecycle(monkeypatch: pytest.MonkeyPatch) -> None:
    """get_session yields an active session and closes it afterwards."""
    mock_session = MagicMock()
    mock_factory = MagicMock(return_value=mock_session)

    monkeypatch.setattr("app.db.SessionLocal", mock_factory)

    generator = get_session()
    session = next(generator)
    assert session is mock_session
    mock_session.close.assert_not_called()

    # Finish the generator
    with pytest.raises(StopIteration):
        next(generator)

    mock_session.close.assert_called_once()


def test_get_sync_session_lifecycle(monkeypatch: pytest.MonkeyPatch) -> None:
    """get_sync_session creates and returns a database session."""
    mock_session = MagicMock()
    mock_factory = MagicMock(return_value=mock_session)
    monkeypatch.setattr("app.db.SessionLocal", mock_factory)

    session = get_sync_session(timeout_ms=5000)
    assert session is mock_session
