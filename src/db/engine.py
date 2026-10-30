"""SQLAlchemy engine, session factory та helper для підключення до PostgreSQL."""

import os
from collections.abc import Generator

from sqlalchemy import create_engine, event
from sqlalchemy.orm import Session, sessionmaker

_engine = None
_SessionLocal = None


def get_database_url() -> str:
    """Повертає DATABASE_URL зі змінних середовища.

    Підтримує форм DATABASES_URL=postgresql://...
    та DATABASE_URL=postgresql+psycopg2://...
    Секрети передаються виключно через змінні середовища (ADR-002).
    """
    url = os.getenv("DATABASE_URL", "").strip()
    if not url:
        raise RuntimeError(
            "DATABASE_URL не задано. "
            "Виставте змінну середовища перед запуском застосунку."
        )
    # Переконуємося що використовується psycopg2 драйвер
    if url.startswith("postgresql://"):
        url = url.replace("postgresql://", "postgresql+psycopg2://", 1)
    return url


def get_engine():
    """Повертає або ледачо створює глобальний Engine."""
    global _engine
    if _engine is None:
        url = get_database_url()
        _engine = create_engine(
            url,
            pool_pre_ping=True,
            pool_size=5,
            max_overflow=10,
            echo=os.getenv("SQL_ECHO", "false").strip().lower() in {"1", "true", "yes"},
        )

        @event.listens_for(_engine, "connect")
        def set_search_path(dbapi_connection, connection_record):
            """Встановлює search_path для нових з'єднань."""
            cursor = dbapi_connection.cursor()
            cursor.execute("SET search_path TO public")
            cursor.close()

    return _engine


def get_session_factory() -> sessionmaker:
    """Повертає або ледачо створює глобальний SessionLocal."""
    global _SessionLocal
    if _SessionLocal is None:
        _SessionLocal = sessionmaker(
            bind=get_engine(),
            autocommit=False,
            autoflush=False,
            expire_on_commit=False,
        )
    return _SessionLocal


def get_db_session() -> Generator[Session, None, None]:
    """FastAPI-залежність: відкриває сесію і гарантує закриття після запиту."""
    factory = get_session_factory()
    session: Session = factory()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()
