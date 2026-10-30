"""Початкова Alembic-міграція: створення схеми PostgreSQL (ADR-002, data-model.md).

Revision ID: 0001_initial_schema
Revises: —
Create Date: 2026-10-30
"""

from __future__ import annotations

import uuid

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0001_initial"
down_revision: str | None = None
branch_labels: str | tuple[str, ...] | None = None
depends_on: str | tuple[str, ...] | None = None


def upgrade() -> None:
    # --- ENUM types ---
    user_role = postgresql.ENUM("USER", "ADMIN", name="user_role", create_type=True)
    listing_condition = postgresql.ENUM(
        "NEW", "LIKE_NEW", "GOOD", "USED", name="listing_condition", create_type=True
    )
    listing_status = postgresql.ENUM(
        "ACTIVE",
        "WITHDRAWN",
        "REMOVED_BY_MODERATOR",
        "RESERVED",
        "SOLD",
        name="listing_status",
        create_type=True,
    )
    suggestion_status = postgresql.ENUM(
        "PENDING",
        "APPROVED",
        "REJECTED",
        name="suggestion_status",
        create_type=True,
    )
    moderation_action_type = postgresql.ENUM(
        "WITHDRAW_LISTING",
        "BLOCK_USER",
        "UNBLOCK_USER",
        "APPROVE_CATEGORY",
        "REJECT_CATEGORY",
        name="moderation_action_type",
        create_type=True,
    )

    bind = op.get_bind()
    if bind.dialect.name == "postgresql":
        user_role.create(bind, checkfirst=True)
        listing_condition.create(bind, checkfirst=True)
        listing_status.create(bind, checkfirst=True)
        suggestion_status.create(bind, checkfirst=True)
        moderation_action_type.create(bind, checkfirst=True)

    # --- users ---
    op.create_table(
        "users",
        sa.Column(
            "user_id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            default=uuid.uuid4,
        ),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("entra_object_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("email", sa.String(320), nullable=False),
        sa.Column("display_name", sa.String(200), nullable=False),
        sa.Column(
            "role",
            sa.Enum("USER", "ADMIN", name="user_role", create_type=False),
            nullable=False,
            server_default="USER",
        ),
        sa.Column("is_blocked", sa.Boolean, nullable=False, server_default=sa.false()),
        sa.Column(
            "display_name_customized",
            sa.Boolean,
            nullable=False,
            server_default=sa.false(),
        ),
        sa.Column("avatar_url", sa.String(500), nullable=True),
        sa.Column("contact", sa.String(300), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.UniqueConstraint(
            "tenant_id", "entra_object_id", name="uq_users_entra_identity"
        ),
        sa.UniqueConstraint("email", name="uq_users_email"),
    )
    op.create_index("ix_users_email", "users", ["email"])
    op.create_index(
        "ix_users_entra_identity",
        "users",
        ["tenant_id", "entra_object_id"],
    )

    # --- categories ---
    op.create_table(
        "categories",
        sa.Column("category_id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("name", sa.String(200), nullable=False),
        sa.Column("slug", sa.String(200), nullable=False),
        sa.Column("description", sa.Text, nullable=True),
        sa.Column("is_active", sa.Boolean, nullable=False, server_default=sa.true()),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.UniqueConstraint("name", name="uq_categories_name"),
        sa.UniqueConstraint("slug", name="uq_categories_slug"),
    )
    op.create_index("ix_categories_is_active", "categories", ["is_active"])

    # --- category_suggestions ---
    op.create_table(
        "category_suggestions",
        sa.Column("suggestion_id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("name", sa.String(40), nullable=False),
        sa.Column(
            "proposer_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.user_id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "status",
            sa.Enum(
                "PENDING",
                "APPROVED",
                "REJECTED",
                name="suggestion_status",
                create_type=False,
            ),
            nullable=False,
            server_default="PENDING",
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column("resolved_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index(
        "ix_category_suggestions_status", "category_suggestions", ["status"]
    )

    # --- listings ---
    op.create_table(
        "listings",
        sa.Column("listing_id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("title", sa.String(200), nullable=False),
        sa.Column("description", sa.Text, nullable=False),
        sa.Column("price", sa.Float, nullable=False),
        sa.Column(
            "category_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("categories.category_id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("contact", sa.Text, nullable=False),
        sa.Column(
            "user_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.user_id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "condition",
            sa.Enum(
                "NEW",
                "LIKE_NEW",
                "GOOD",
                "USED",
                name="listing_condition",
                create_type=False,
            ),
            nullable=False,
            server_default="GOOD",
        ),
        sa.Column(
            "status",
            sa.Enum(
                "ACTIVE",
                "WITHDRAWN",
                "REMOVED_BY_MODERATOR",
                "RESERVED",
                "SOLD",
                name="listing_status",
                create_type=False,
            ),
            nullable=False,
            server_default="ACTIVE",
        ),
        sa.Column(
            "suggested_category_id", postgresql.UUID(as_uuid=True), nullable=True
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.CheckConstraint("price >= 0", name="ck_listings_price_non_negative"),
    )
    op.create_index("ix_listings_user_id", "listings", ["user_id"])
    op.create_index("ix_listings_category_id", "listings", ["category_id"])
    op.create_index("ix_listings_status", "listings", ["status"])
    op.create_index("ix_listings_created_at", "listings", ["created_at"])

    # --- listing_images ---
    op.create_table(
        "listing_images",
        sa.Column("image_id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "listing_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("listings.listing_id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("image_url", sa.String(500), nullable=False),
        sa.Column("thumbnail_url", sa.String(500), nullable=True),
        sa.Column("storage_key", sa.String(500), nullable=True),
        sa.Column("display_order", sa.Integer, nullable=False, server_default="0"),
        sa.Column("width", sa.Integer, nullable=True),
        sa.Column("height", sa.Integer, nullable=True),
        sa.Column("thumbnail_width", sa.Integer, nullable=True),
        sa.Column("thumbnail_height", sa.Integer, nullable=True),
    )
    op.create_index("ix_listing_images_listing_id", "listing_images", ["listing_id"])

    # --- favorites ---
    op.create_table(
        "favorites",
        sa.Column(
            "user_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.user_id", ondelete="CASCADE"),
            primary_key=True,
        ),
        sa.Column(
            "listing_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("listings.listing_id", ondelete="CASCADE"),
            primary_key=True,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
    )

    # --- moderation_actions ---
    op.create_table(
        "moderation_actions",
        sa.Column("action_id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "moderator_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.user_id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column(
            "action_type",
            sa.Enum(
                "WITHDRAW_LISTING",
                "BLOCK_USER",
                "UNBLOCK_USER",
                "APPROVE_CATEGORY",
                "REJECT_CATEGORY",
                name="moderation_action_type",
                create_type=False,
            ),
            nullable=False,
        ),
        sa.Column("reason", sa.String(500), nullable=False),
        sa.Column(
            "listing_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("listings.listing_id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column(
            "target_user_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.user_id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column(
            "suggestion_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("category_suggestions.suggestion_id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
    )
    op.create_index(
        "ix_moderation_actions_listing_id",
        "moderation_actions",
        ["listing_id"],
    )
    op.create_index(
        "ix_moderation_actions_target_user_id",
        "moderation_actions",
        ["target_user_id"],
    )


def downgrade() -> None:
    op.drop_table("moderation_actions")
    op.drop_table("favorites")
    op.drop_table("listing_images")
    op.drop_table("listings")
    op.drop_table("category_suggestions")
    op.drop_table("categories")
    op.drop_table("users")

    # Drop enum types
    bind = op.get_bind()
    if bind.dialect.name == "postgresql":
        for name in [
            "moderation_action_type",
            "suggestion_status",
            "listing_status",
            "listing_condition",
            "user_role",
        ]:
            postgresql.ENUM(name=name).drop(bind, checkfirst=True)
