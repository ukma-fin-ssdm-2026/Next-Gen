"""Поля розгляду пропозиції категорії (FR-015).

Доменна модель CategorySuggestion зберігає, хто і коли розглянув пропозицію,
причину відхилення та створену категорію. Початкова схема мала лише
`resolved_at`, тому збереження пропозицій у PostgreSQL падало з 500.

Revision ID: 0002_suggestion_review
Revises: 0001_initial
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0002_suggestion_review"
down_revision: str | None = "0001_initial"
branch_labels = None
depends_on = None

TABLE = "category_suggestions"


def upgrade() -> None:
    with op.batch_alter_table(TABLE) as batch:
        batch.alter_column("resolved_at", new_column_name="reviewed_at")
        batch.add_column(sa.Column("reason", sa.Text, nullable=True))
        batch.add_column(
            sa.Column("category_id", postgresql.UUID(as_uuid=True), nullable=True)
        )
        batch.add_column(
            sa.Column("reviewed_by", postgresql.UUID(as_uuid=True), nullable=True)
        )
        batch.create_foreign_key(
            "fk_category_suggestions_category_id",
            "categories",
            ["category_id"],
            ["category_id"],
            ondelete="SET NULL",
        )
        batch.create_foreign_key(
            "fk_category_suggestions_reviewed_by",
            "users",
            ["reviewed_by"],
            ["user_id"],
            ondelete="SET NULL",
        )


def downgrade() -> None:
    with op.batch_alter_table(TABLE) as batch:
        batch.drop_constraint("fk_category_suggestions_reviewed_by", type_="foreignkey")
        batch.drop_constraint("fk_category_suggestions_category_id", type_="foreignkey")
        batch.drop_column("reviewed_by")
        batch.drop_column("category_id")
        batch.drop_column("reason")
        batch.alter_column("reviewed_at", new_column_name="resolved_at")
