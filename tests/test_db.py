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


def test_statement_timeout_pg_sleep() -> None:
    """pg_sleep query exceeding DB_STATEMENT_TIMEOUT_MS raises a statement timeout error."""
    from sqlalchemy import text

    from app.db import engine, get_session

    if engine.dialect.name != "postgresql":
        pytest.skip("pg_sleep test requires PostgreSQL")

    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
    except Exception as exc:
        pytest.skip(f"PostgreSQL connection unavailable for live pg_sleep test: {exc}")

    gen = get_session()
    session = next(gen)
    try:
        with pytest.raises(OperationalError) as exc_info:
            # Read session sets statement_timeout to 2000ms. Sleeping 3s triggers timeout.
            session.execute(text("SELECT pg_sleep(3)"))

        assert is_timeout_error(exc_info.value) is True
    finally:
        try:
            next(gen)
        except StopIteration:
            pass
