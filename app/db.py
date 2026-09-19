"""Database engine, session factory, and session dependency management.

Configures connection pooling, statement timeouts for read sessions (NFR-014),
and session lifecycles for FastAPI dependencies and background ingestion (P1-004).
"""

from collections.abc import Generator

from sqlalchemy import create_engine, text
from sqlalchemy.exc import DatabaseError, OperationalError
from sqlalchemy.orm import Session, declarative_base, sessionmaker

from app.config import DB_STATEMENT_TIMEOUT_MS, settings

# SQLAlchemy 2.0 declarative base
Base = declarative_base()

# Connection engine
# Uses psycopg3 via the postgresql+psycopg driver specified in DATABASE_URL
engine = create_engine(
    settings.database_url,
    pool_pre_ping=True,
    future=True,
)

# Standard sessionmaker
SessionLocal = sessionmaker(
    bind=engine,
    autocommit=False,
    autoflush=False,
    expire_on_commit=False,
    future=True,
)


def get_session() -> Generator[Session, None, None]:
    """Provide a transactional database session for read-path requests.

    Sets a 2-second statement timeout (DB_STATEMENT_TIMEOUT_MS) so queries
    fail fast rather than hanging the API request (NFR-014).
    """
    session: Session = SessionLocal()
    try:
        # Enforce read-path statement timeout on PostgreSQL connections
        if engine.dialect.name == "postgresql":
            session.execute(text(f"SET statement_timeout = {int(DB_STATEMENT_TIMEOUT_MS)}"))
        yield session
    finally:
        session.close()


def get_sync_session(timeout_ms: int = 60000) -> Session:
    """Create a database session with an extended timeout for background sync runs."""
    session: Session = SessionLocal()
    if engine.dialect.name == "postgresql":
        session.execute(text(f"SET statement_timeout = {int(timeout_ms)}"))
    return session


def is_timeout_error(exc: Exception) -> bool:
    """Determine whether an exception was caused by a database statement timeout.

    Used by read-path tools to map query failures to TIMEOUT (FR-033).
    if isinstance(exc, (OperationalError, DatabaseError)):
        msg = str(exc).lower()
        return (
            "statement timeout" in msg
            or "canceling statement due to statement timeout" in msg
            or "57014" in msg
        )
    return False
