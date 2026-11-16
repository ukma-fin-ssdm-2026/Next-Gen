"""Скарги на повідомлення чату зі знімком тексту (ADR-005)."""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0009_message_reports"
down_revision = "0008_message_reply_to"
branch_labels = None
depends_on = None


def _uuid() -> postgresql.UUID:
    return postgresql.UUID(as_uuid=True)


def upgrade() -> None:
    op.create_table(
        "message_reports",
        sa.Column("report_id", _uuid(), primary_key=True),
        sa.Column("message_id", _uuid(), nullable=False),
        sa.Column("conversation_id", _uuid(), nullable=False),
        sa.Column(
            "reporter_id",
            _uuid(),
            sa.ForeignKey("users.user_id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "reported_user_id",
            _uuid(),
            sa.ForeignKey("users.user_id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("body_snapshot", sa.Text(), nullable=False),
        sa.Column("reason", sa.String(20), nullable=False),
        sa.Column("details", sa.Text(), nullable=False, server_default=""),
        sa.Column("status", sa.String(10), nullable=False, server_default="OPEN"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column(
            "resolved_by",
            _uuid(),
            sa.ForeignKey("users.user_id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("resolved_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("resolution_note", sa.Text(), nullable=False, server_default=""),
        sa.UniqueConstraint(
            "message_id", "reporter_id", name="uq_message_reports_message_reporter"
        ),
    )
    op.create_index("ix_message_reports_status", "message_reports", ["status"])


def downgrade() -> None:
    op.drop_index("ix_message_reports_status", table_name="message_reports")
    op.drop_table("message_reports")
