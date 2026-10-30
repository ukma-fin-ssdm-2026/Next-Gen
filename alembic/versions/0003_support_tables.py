"""Скарги, звернення, журнал дій і причина блокування користувача.

Додає `users.block_reason` та `users.blocked_at` (список заблокованих із
причиною, що переживає перезапуск), а також таблиці `complaints` (FR-016),
`feedback_messages` (FR-017) і `activity_events` (FR-018).

Revision ID: 0003_support_tables
Revises: 0002_suggestion_review
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0003_support_tables"
down_revision: str | None = "0002_suggestion_review"
branch_labels = None
depends_on = None


def _uuid() -> postgresql.UUID:
    return postgresql.UUID(as_uuid=True)


def upgrade() -> None:
    with op.batch_alter_table("users") as batch:
        batch.add_column(sa.Column("block_reason", sa.Text, nullable=True))
        batch.add_column(
            sa.Column("blocked_at", sa.DateTime(timezone=True), nullable=True)
        )

    op.create_table(
        "complaints",
        sa.Column("complaint_id", _uuid(), primary_key=True),
        sa.Column(
            "listing_id",
            _uuid(),
            sa.ForeignKey("listings.listing_id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "reporter_id",
            _uuid(),
            sa.ForeignKey("users.user_id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("reason", sa.String(20), nullable=False),
        sa.Column("details", sa.Text, nullable=False),
        sa.Column("status", sa.String(10), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column(
            "resolved_by",
            _uuid(),
            sa.ForeignKey("users.user_id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("resolved_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("resolution_note", sa.Text, nullable=False),
        sa.UniqueConstraint(
            "listing_id", "reporter_id", name="uq_complaints_listing_reporter"
        ),
    )
    op.create_index("ix_complaints_status", "complaints", ["status"])

    op.create_table(
        "feedback_messages",
        sa.Column("feedback_id", _uuid(), primary_key=True),
        sa.Column(
            "user_id",
            _uuid(),
            sa.ForeignKey("users.user_id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("subject", sa.String(120), nullable=False),
        sa.Column("message", sa.Text, nullable=False),
        sa.Column("status", sa.String(10), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column(
            "resolved_by",
            _uuid(),
            sa.ForeignKey("users.user_id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("resolved_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_feedback_messages_status", "feedback_messages", ["status"])

    op.create_table(
        "activity_events",
        sa.Column("event_id", _uuid(), primary_key=True),
        sa.Column(
            "actor_id",
            _uuid(),
            sa.ForeignKey("users.user_id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("actor_role", sa.String(10), nullable=False),
        sa.Column("action_type", sa.String(30), nullable=False),
        sa.Column("listing_id", _uuid(), nullable=True),
        sa.Column("details", sa.String(300), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index(
        "ix_activity_events_role_created",
        "activity_events",
        ["actor_role", "created_at"],
    )


def downgrade() -> None:
    op.drop_table("activity_events")
    op.drop_table("feedback_messages")
    op.drop_table("complaints")
    with op.batch_alter_table("users") as batch:
        batch.drop_column("blocked_at")
        batch.drop_column("block_reason")
