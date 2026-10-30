"""Додає стан товару FOR_PARTS («На запчастини») до enum listing_condition.

Revision ID: 0004_condition_for_parts
Revises: 0003_support_tables
"""

from __future__ import annotations

from alembic import op

revision: str = "0004_condition_for_parts"
down_revision: str | None = "0003_support_tables"
branch_labels = None
depends_on = None


def _is_postgres() -> bool:
    return op.get_bind().dialect.name == "postgresql"


def upgrade() -> None:
    if not _is_postgres():
        return  # SQLite (тести) зберігає enum як VARCHAR без обмежень значень
    # ADD VALUE не можна виконувати в одній транзакції з використанням нового
    # значення, тому окремий autocommit-блок.
    with op.get_context().autocommit_block():
        op.execute("ALTER TYPE listing_condition ADD VALUE IF NOT EXISTS 'FOR_PARTS'")


def downgrade() -> None:
    if not _is_postgres():
        return
    # Значення з enum у PostgreSQL видалити не можна; повертаємо дані до USED,
    # щоб старий код не зустрічав невідомого стану.
    op.execute("UPDATE listings SET condition = 'USED' WHERE condition = 'FOR_PARTS'")
