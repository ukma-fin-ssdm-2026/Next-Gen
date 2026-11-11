"""SQLAlchemy engine, session factory та helper для підключення до PostgreSQL."""

import os
from collections.abc import Generator

from sqlalchemy import create_engine, event
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker

# REL-03: без тайм-аутів запит при недоступному PostgreSQL висів до системного
# TCP-таймауту (~120 с) і тримав потік. Тепер підключення і очікування вільного
# з'єднання в пулі обмежені, а API відповідає 503 (див. src/api/main.py).
DEFAULT_DB_CONNECT_TIMEOUT_SECONDS = 5
DEFAULT_DB_POOL_TIMEOUT_SECONDS = 10

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


def read_timeout_seconds(name: str, default: int) -> int:
    """Читає тайм-аут у цілих секундах зі змінної середовища.

    Guard clause: нуль, від'ємне чи нечислове значення зупиняє старт застосунку
    (fail fast), щоб помилка конфігурації не вимкнула тайм-аут непомітно.
    """
    raw = os.getenv(name, "").strip()
    if not raw:
        return default
    try:
        value = int(raw)
    except ValueError:
        raise RuntimeError(
            f"{name} має бути цілим числом секунд, отримано {raw!r}"
        ) from None
    if value <= 0:
        raise RuntimeError(f"{name} має бути більшим за 0, отримано {value}")
    return value


def build_engine(url: str, *, connect_timeout: int, pool_timeout: int) -> Engine:
    """Створює Engine з обмеженим часом підключення та очікування пулу."""
    return create_engine(
        url,
        pool_pre_ping=True,
        pool_size=5,
        max_overflow=10,
        pool_timeout=pool_timeout,
        connect_args={"connect_timeout": connect_timeout},
        echo=os.getenv("SQL_ECHO", "false").strip().lower() in {"1", "true", "yes"},
    )


def get_engine():
    """Повертає або ледачо створює глобальний Engine."""
    global _engine
    if _engine is None:
        _engine = build_engine(
            get_database_url(),
            connect_timeout=read_timeout_seconds(
                "DB_CONNECT_TIMEOUT_SECONDS", DEFAULT_DB_CONNECT_TIMEOUT_SECONDS
            ),
            pool_timeout=read_timeout_seconds(
                "DB_POOL_TIMEOUT_SECONDS", DEFAULT_DB_POOL_TIMEOUT_SECONDS
            ),
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
