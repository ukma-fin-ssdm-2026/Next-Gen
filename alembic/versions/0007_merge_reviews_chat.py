"""Зводить гілки міграцій і зберігає стан модерації та повну причину."""

import sqlalchemy as sa
from alembic import op

revision = "0007_merge_reviews_chat"
down_revision = ("0005_seller_reviews", "0006_chat_tables")
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("seller_reviews") as batch:
        batch.add_column(sa.Column("deleted_at", sa.DateTime(timezone=True)))
        batch.create_check_constraint(
            "ck_seller_reviews_deleted_hidden",
            "deleted_at IS NULL OR status = 'HIDDEN'",
        )
    op.add_column("activity_events", sa.Column("moderation_reason", sa.String(500)))


def downgrade() -> None:
    op.drop_column("activity_events", "moderation_reason")
    with op.batch_alter_table("seller_reviews") as batch:
        batch.drop_constraint("ck_seller_reviews_deleted_hidden", type_="check")
        batch.drop_column("deleted_at")
