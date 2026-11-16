"""Додає оцінки продавців та індекс для рухомого ліміту (ADR-004)."""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0005_seller_reviews"
down_revision = "0004_condition_for_parts"
branch_labels = None
depends_on = None

review_status = sa.Enum("VISIBLE", "HIDDEN", name="seller_review_status")


def upgrade() -> None:
    op.create_table(
        "seller_reviews",
        sa.Column("review_id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "seller_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.user_id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "author_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.user_id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "listing_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("listings.listing_id", ondelete="SET NULL"),
        ),
        sa.Column("rating", sa.SmallInteger, nullable=False),
        sa.Column("status", review_status, nullable=False, server_default="VISIBLE"),
        sa.Column(
            "hidden_by", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.user_id")
        ),
        sa.Column("hidden_at", sa.DateTime(timezone=True)),
        sa.Column("hidden_reason", sa.Text),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint(
            "author_id", "seller_id", name="uq_seller_reviews_author_seller"
        ),
        sa.CheckConstraint("author_id <> seller_id", name="ck_seller_reviews_not_self"),
        sa.CheckConstraint("rating BETWEEN 1 AND 5", name="ck_seller_reviews_rating"),
        sa.CheckConstraint(
            "(status = 'VISIBLE' AND hidden_by IS NULL AND hidden_at IS NULL "
            "AND hidden_reason IS NULL) OR "
            "(status = 'HIDDEN' AND hidden_by IS NOT NULL AND hidden_at IS NOT NULL "
            "AND hidden_reason IS NOT NULL "
            "AND length(trim(hidden_reason)) BETWEEN 5 AND 500)",
            name="ck_seller_reviews_moderation",
        ),
    )
    op.create_index(
        "ix_seller_reviews_seller_status", "seller_reviews", ["seller_id", "status"]
    )
    op.create_index(
        "ix_activity_events_actor_action_created",
        "activity_events",
        ["actor_id", "action_type", "created_at"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_activity_events_actor_action_created", table_name="activity_events"
    )
    op.drop_table("seller_reviews")
    review_status.drop(op.get_bind(), checkfirst=True)
