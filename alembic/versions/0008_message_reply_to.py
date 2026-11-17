"""Відповідь на повідомлення: `messages.reply_to_id` (ADR-005)."""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0008_message_reply_to"
down_revision = "0007_merge_reviews_chat"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("messages") as batch:
        batch.add_column(
            sa.Column("reply_to_id", postgresql.UUID(as_uuid=True), nullable=True)
        )
        batch.create_foreign_key(
            "fk_messages_reply_to_id",
            "messages",
            ["reply_to_id"],
            ["message_id"],
            ondelete="SET NULL",
        )


def downgrade() -> None:
    with op.batch_alter_table("messages") as batch:
        batch.drop_constraint("fk_messages_reply_to_id", type_="foreignkey")
        batch.drop_column("reply_to_id")
