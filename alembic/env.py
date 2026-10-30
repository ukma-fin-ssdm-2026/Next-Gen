"""Alembic environment — підключає SQLAlchemy metadata та DATABASE_URL."""

import os
import sys
from logging.config import fileConfig
from pathlib import Path

from alembic import context
from sqlalchemy import engine_from_config, pool

# Додаємо корінь проєкту до sys.path, щоб знайти пакет src
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.db.models import Base  # noqa: E402

config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata


def get_url() -> str:
    """Пріоритет: явний sqlalchemy.url у Config → DATABASE_URL → alembic.ini."""
    # Якщо sqlalchemy.url явно передано програмно (наприклад, у тестах з SQLite):
    url = config.get_main_option("sqlalchemy.url", "").strip()
    if not url or "driver://user:pass@localhost/dbname" in url:
        url = os.getenv("DATABASE_URL", "").strip()
    if not url:
        url = config.get_main_option("sqlalchemy.url", "").strip()
    if not url:
        raise RuntimeError(
            "DATABASE_URL не задано. Виставте змінну середовища або "
            "sqlalchemy.url в alembic.ini."
        )
    # Переконуємося, що використовується psycopg2 драйвер для синхронного Alembic
    if url.startswith("postgresql://"):
        url = url.replace("postgresql://", "postgresql+psycopg2://", 1)
    return url


def run_migrations_offline() -> None:
    """Генерує SQL-скрипт без реального з'єднання з БД."""
    url = get_url()
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        compare_type=True,
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """Виконує міграції з реальним з'єднанням."""
    cfg = config.get_section(config.config_ini_section) or {}
    cfg["sqlalchemy.url"] = get_url()
    connectable = engine_from_config(
        cfg,
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )
    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            compare_type=True,
        )
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
