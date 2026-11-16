"""Таблиці вбудованого чату: `conversations` і `messages` (ADR-005).

Розмова — пара користувачів у впорядкованому вигляді (`user_low_id` <
`user_high_id`, унікальна); повідомлення незмінні й упорядковані лише за
`(created_at, message_id)`. Посилання на оголошення — `ON DELETE SET NULL`,
щоб історія розмови переживала видалення оголошення.

Revision ID: 0006_chat_tables
Revises: 0004_condition_for_parts

За ADR-005 чат іде після міграції оцінок `0005_seller_reviews`. Поки її немає
в `main`, ланцюжок продовжує `0004`; після злиття оцінок `down_revision`
треба змінити на "0005_seller_reviews", інакше Alembic побачить дві голови.
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0006_chat_tables"
down_revision: str | None = "0004_condition_for_parts"
branch_labels = None
depends_on = None


def _uuid() -> postgresql.UUID:
    return postgresql.UUID(as_uuid=True)


def upgrade() -> None:
    op.create_table(
        "conversations",
        sa.Column("conversation_id", _uuid(), primary_key=True),
        sa.Column(
            "user_low_id",
            _uuid(),
            sa.ForeignKey("users.user_id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "user_high_id",
            _uuid(),
            sa.ForeignKey("users.user_id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("last_message_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("low_last_read_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("low_last_read_message_id", _uuid(), nullable=True),
        sa.Column("high_last_read_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("high_last_read_message_id", _uuid(), nullable=True),
        sa.UniqueConstraint(
            "user_low_id", "user_high_id", name="uq_conversations_pair"
        ),
        sa.CheckConstraint(
            "user_low_id < user_high_id", name="ck_conversations_pair_order"
        ),
    )
    op.create_index(
        "ix_conversations_low_activity",
        "conversations",
        ["user_low_id", "last_message_at"],
    )
    op.create_index(
        "ix_conversations_high_activity",
        "conversations",
        ["user_high_id", "last_message_at"],
    )

    op.create_table(
        "messages",
        sa.Column("message_id", _uuid(), primary_key=True),
        sa.Column(
            "conversation_id",
            _uuid(),
            sa.ForeignKey("conversations.conversation_id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "sender_id",
            _uuid(),
            sa.ForeignKey("users.user_id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("body", sa.Text, nullable=False),
        sa.Column(
            "listing_id",
            _uuid(),
            sa.ForeignKey("listings.listing_id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "length(body) BETWEEN 1 AND 1000", name="ck_messages_body_length"
        ),
    )
    op.create_index(
        "ix_messages_conversation_order",
        "messages",
        ["conversation_id", "created_at", "message_id"],
    )
    op.create_index(
        "ix_messages_sender_created", "messages", ["sender_id", "created_at"]
    )


def downgrade() -> None:
    op.drop_table("messages")
    op.drop_table("conversations")
