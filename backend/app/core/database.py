from collections.abc import Generator

from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session, sessionmaker

from app.core.config import settings
from app.core.logging import logger
from app.models.base import Base

# Configure connection and query timeouts for PostgreSQL/psycopg driver
connect_args = {}
if "postgresql" in settings.DATABASE_URL:
    connect_args = {
        "connect_timeout": 3,
        "options": "-c statement_timeout=3000",
    }

engine = create_engine(
    settings.DATABASE_URL,
    echo=settings.DB_ECHO,
    pool_pre_ping=True,
    pool_size=10,
    max_overflow=20,
    connect_args=connect_args,
)

SessionLocal = sessionmaker(
    autocommit=False,
    autoflush=False,
    bind=engine,
)


def get_db() -> Generator[Session, None, None]:
    """Dependency for obtaining a database session per request.

    Explicitly rolls back any uncommitted/failed transaction on error before
    closing.
    """
    db = SessionLocal()
    try:
        yield db
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


def check_db_connection() -> bool:
    """Safely verify connectivity to PostgreSQL database with timeout protection."""
    try:
        with engine.connect() as connection:
            connection.execute(text("SELECT 1"))
        return True
    except Exception as exc:
        logger.warning(f"Database connection check failed: {exc}")
        return False


__all__ = ["Base", "SessionLocal", "check_db_connection", "engine", "get_db"]
