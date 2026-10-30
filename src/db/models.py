"""SQLAlchemy ORM-моделі для PostgreSQL (ADR-002, data-model.md).

Файл містить декларативні ORM-класи для всіх таблиць схеми.
Не зберігати бінарні файли фотографій у БД — лише ключ/шлях та metadata.
"""

import uuid
from datetime import datetime, timezone

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    Enum as SAEnum,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class Base(DeclarativeBase):
    """Базовий клас для всіх ORM-моделей."""

    pass


# ---------------------------------------------------------------------------
# User
# ---------------------------------------------------------------------------


class UserRow(Base):
    """Локальний профіль користувача, прив'язаний до Microsoft Entra ID."""

    __tablename__ = "users"
    __table_args__ = (
        UniqueConstraint(
            "tenant_id", "entra_object_id", name="uq_users_entra_identity"
        ),
        UniqueConstraint("email", name="uq_users_email"),
        Index("ix_users_email", "email"),
        Index("ix_users_entra_identity", "tenant_id", "entra_object_id"),
    )

    user_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    tenant_id: Mapped[uuid.UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False)
    entra_object_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True), nullable=False
    )
    email: Mapped[str] = mapped_column(String(320), nullable=False)
    display_name: Mapped[str] = mapped_column(String(200), nullable=False)
    role: Mapped[str] = mapped_column(
        SAEnum("USER", "ADMIN", name="user_role"), nullable=False, default="USER"
    )
    is_blocked: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    display_name_customized: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False
    )
    avatar_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    contact: Mapped[str | None] = mapped_column(String(300), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_utcnow
    )
    block_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    blocked_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    listings: Mapped[list["ListingRow"]] = relationship(
        "ListingRow", back_populates="owner", lazy="select"
    )
    favorites: Mapped[list["FavoriteRow"]] = relationship(
        "FavoriteRow", back_populates="user", lazy="select"
    )
    moderation_actions_as_moderator: Mapped[list["ModerationActionRow"]] = relationship(
        "ModerationActionRow",
        foreign_keys="[ModerationActionRow.moderator_id]",
        back_populates="moderator",
        lazy="select",
    )
    moderation_actions_as_target: Mapped[list["ModerationActionRow"]] = relationship(
        "ModerationActionRow",
        foreign_keys="[ModerationActionRow.target_user_id]",
        back_populates="target_user",
        lazy="select",
    )


# ---------------------------------------------------------------------------
# Category
# ---------------------------------------------------------------------------


class CategoryRow(Base):
    """Категорія оголошень (FR-012)."""

    __tablename__ = "categories"
    __table_args__ = (
        UniqueConstraint("name", name="uq_categories_name"),
        UniqueConstraint("slug", name="uq_categories_slug"),
        Index("ix_categories_is_active", "is_active"),
    )

    category_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    slug: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_utcnow
    )

    listings: Mapped[list["ListingRow"]] = relationship(
        "ListingRow", back_populates="category", lazy="select"
    )


# ---------------------------------------------------------------------------
# CategorySuggestion
# ---------------------------------------------------------------------------


class CategorySuggestionRow(Base):
    """Пропозиція нової категорії від продавця (FR-015 / US-010)."""

    __tablename__ = "category_suggestions"
    __table_args__ = (Index("ix_category_suggestions_status", "status"),)

    suggestion_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    name: Mapped[str] = mapped_column(String(40), nullable=False)
    proposer_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("users.user_id", ondelete="CASCADE"),
        nullable=False,
    )
    status: Mapped[str] = mapped_column(
        SAEnum("PENDING", "APPROVED", "REJECTED", name="suggestion_status"),
        nullable=False,
        default="PENDING",
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_utcnow
    )
    reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    category_id: Mapped[uuid.UUID | None] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey(
            "categories.category_id",
            ondelete="SET NULL",
            name="fk_category_suggestions_category_id",
        ),
        nullable=True,
    )
    reviewed_by: Mapped[uuid.UUID | None] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey(
            "users.user_id",
            ondelete="SET NULL",
            name="fk_category_suggestions_reviewed_by",
        ),
        nullable=True,
    )
    reviewed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    moderation_actions: Mapped[list["ModerationActionRow"]] = relationship(
        "ModerationActionRow",
        foreign_keys="[ModerationActionRow.suggestion_id]",
        back_populates="suggestion",
        lazy="select",
    )


# ---------------------------------------------------------------------------
# Listing
# ---------------------------------------------------------------------------


class ListingRow(Base):
    """Оголошення маркетплейсу (FR-002..FR-008, FR-015)."""

    __tablename__ = "listings"
    __table_args__ = (
        CheckConstraint("price >= 0", name="ck_listings_price_non_negative"),
        Index("ix_listings_user_id", "user_id"),
        Index("ix_listings_category_id", "category_id"),
        Index("ix_listings_status", "status"),
        Index("ix_listings_created_at", "created_at"),
    )

    listing_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    price: Mapped[float] = mapped_column(Float, nullable=False)
    category_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("categories.category_id", ondelete="RESTRICT"),
        nullable=False,
    )
    contact: Mapped[str] = mapped_column(Text, nullable=False)
    user_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("users.user_id", ondelete="CASCADE"),
        nullable=False,
    )
    condition: Mapped[str] = mapped_column(
        SAEnum("NEW", "LIKE_NEW", "GOOD", "USED", name="listing_condition"),
        nullable=False,
        default="GOOD",
    )
    status: Mapped[str] = mapped_column(
        SAEnum(
            "ACTIVE",
            "WITHDRAWN",
            "REMOVED_BY_MODERATOR",
            "RESERVED",
            "SOLD",
            name="listing_status",
        ),
        nullable=False,
        default="ACTIVE",
    )
    suggested_category_id: Mapped[uuid.UUID | None] = mapped_column(
        PGUUID(as_uuid=True), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_utcnow
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_utcnow, onupdate=_utcnow
    )

    owner: Mapped["UserRow"] = relationship(
        "UserRow", back_populates="listings", lazy="select"
    )
    category: Mapped["CategoryRow"] = relationship(
        "CategoryRow", back_populates="listings", lazy="select"
    )
    images: Mapped[list["ListingImageRow"]] = relationship(
        "ListingImageRow",
        back_populates="listing",
        cascade="all, delete-orphan",
        order_by="ListingImageRow.display_order",
        lazy="selectin",
    )
    favorites: Mapped[list["FavoriteRow"]] = relationship(
        "FavoriteRow",
        back_populates="listing",
        cascade="all, delete-orphan",
        lazy="select",
    )
    moderation_actions: Mapped[list["ModerationActionRow"]] = relationship(
        "ModerationActionRow",
        foreign_keys="[ModerationActionRow.listing_id]",
        back_populates="listing",
        lazy="select",
    )


# ---------------------------------------------------------------------------
# ListingImage
# ---------------------------------------------------------------------------


class ListingImageRow(Base):
    """Зображення, прикріплене до оголошення (FR-002). Бінарні дані не зберігаються."""

    __tablename__ = "listing_images"
    __table_args__ = (Index("ix_listing_images_listing_id", "listing_id"),)

    image_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    listing_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("listings.listing_id", ondelete="CASCADE"),
        nullable=False,
    )
    image_url: Mapped[str] = mapped_column(String(500), nullable=False)
    thumbnail_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    storage_key: Mapped[str | None] = mapped_column(String(500), nullable=True)
    display_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    width: Mapped[int | None] = mapped_column(Integer, nullable=True)
    height: Mapped[int | None] = mapped_column(Integer, nullable=True)
    thumbnail_width: Mapped[int | None] = mapped_column(Integer, nullable=True)
    thumbnail_height: Mapped[int | None] = mapped_column(Integer, nullable=True)

    listing: Mapped["ListingRow"] = relationship(
        "ListingRow", back_populates="images", lazy="select"
    )


# ---------------------------------------------------------------------------
# Favorite
# ---------------------------------------------------------------------------


class FavoriteRow(Base):
    """Запис в обраному (FR-009). Складений первинний ключ (user_id, listing_id)."""

    __tablename__ = "favorites"

    user_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("users.user_id", ondelete="CASCADE"),
        primary_key=True,
    )
    listing_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("listings.listing_id", ondelete="CASCADE"),
        primary_key=True,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_utcnow
    )

    user: Mapped["UserRow"] = relationship(
        "UserRow", back_populates="favorites", lazy="select"
    )
    listing: Mapped["ListingRow"] = relationship(
        "ListingRow", back_populates="favorites", lazy="select"
    )


# ---------------------------------------------------------------------------
# ModerationAction
# ---------------------------------------------------------------------------


class ModerationActionRow(Base):
    """Журнал адміністративних дій (FR-011, FR-013, FR-015).

    Append-only: рядки не оновлюються та не видаляються.
    """

    __tablename__ = "moderation_actions"
    __table_args__ = (
        Index("ix_moderation_actions_listing_id", "listing_id"),
        Index("ix_moderation_actions_target_user_id", "target_user_id"),
    )

    action_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    moderator_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("users.user_id", ondelete="RESTRICT"),
        nullable=False,
    )
    action_type: Mapped[str] = mapped_column(
        SAEnum(
            "WITHDRAW_LISTING",
            "BLOCK_USER",
            "UNBLOCK_USER",
            "APPROVE_CATEGORY",
            "REJECT_CATEGORY",
            name="moderation_action_type",
        ),
        nullable=False,
    )
    reason: Mapped[str] = mapped_column(String(500), nullable=False)
    listing_id: Mapped[uuid.UUID | None] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("listings.listing_id", ondelete="SET NULL"),
        nullable=True,
    )
    target_user_id: Mapped[uuid.UUID | None] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("users.user_id", ondelete="SET NULL"),
        nullable=True,
    )
    suggestion_id: Mapped[uuid.UUID | None] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("category_suggestions.suggestion_id", ondelete="SET NULL"),
        nullable=True,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_utcnow
    )

    moderator: Mapped["UserRow"] = relationship(
        "UserRow",
        foreign_keys=[moderator_id],
        back_populates="moderation_actions_as_moderator",
        lazy="select",
    )
    target_user: Mapped["UserRow | None"] = relationship(
        "UserRow",
        foreign_keys=[target_user_id],
        back_populates="moderation_actions_as_target",
        lazy="select",
    )
    listing: Mapped["ListingRow | None"] = relationship(
        "ListingRow",
        foreign_keys=[listing_id],
        back_populates="moderation_actions",
        lazy="select",
    )
    suggestion: Mapped["CategorySuggestionRow | None"] = relationship(
        "CategorySuggestionRow",
        foreign_keys=[suggestion_id],
        back_populates="moderation_actions",
        lazy="select",
    )


# ---------------------------------------------------------------------------
# Complaint / Feedback / ActivityEvent
# ---------------------------------------------------------------------------


class ComplaintRow(Base):
    """Скарга користувача на оголошення (FR-016)."""

    __tablename__ = "complaints"
    __table_args__ = (
        UniqueConstraint(
            "listing_id", "reporter_id", name="uq_complaints_listing_reporter"
        ),
        Index("ix_complaints_status", "status"),
    )

    complaint_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    listing_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("listings.listing_id", ondelete="CASCADE"),
        nullable=False,
    )
    reporter_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("users.user_id", ondelete="CASCADE"),
        nullable=False,
    )
    reason: Mapped[str] = mapped_column(String(20), nullable=False)
    details: Mapped[str] = mapped_column(Text, nullable=False, default="")
    status: Mapped[str] = mapped_column(String(10), nullable=False, default="OPEN")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_utcnow
    )
    resolved_by: Mapped[uuid.UUID | None] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("users.user_id", ondelete="SET NULL"),
        nullable=True,
    )
    resolved_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    resolution_note: Mapped[str] = mapped_column(Text, nullable=False, default="")


class FeedbackRow(Base):
    """Звернення користувача до адміністрації (FR-017)."""

    __tablename__ = "feedback_messages"
    __table_args__ = (Index("ix_feedback_messages_status", "status"),)

    feedback_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("users.user_id", ondelete="CASCADE"),
        nullable=False,
    )
    subject: Mapped[str] = mapped_column(String(120), nullable=False)
    message: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(String(10), nullable=False, default="NEW")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_utcnow
    )
    resolved_by: Mapped[uuid.UUID | None] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("users.user_id", ondelete="SET NULL"),
        nullable=True,
    )
    resolved_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )


class ActivityEventRow(Base):
    """Незмінний запис журналу дій користувача або адміністратора (FR-018)."""

    __tablename__ = "activity_events"
    __table_args__ = (
        Index("ix_activity_events_role_created", "actor_role", "created_at"),
    )

    event_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    actor_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("users.user_id", ondelete="CASCADE"),
        nullable=False,
    )
    actor_role: Mapped[str] = mapped_column(String(10), nullable=False)
    action_type: Mapped[str] = mapped_column(String(30), nullable=False)
    listing_id: Mapped[uuid.UUID | None] = mapped_column(
        PGUUID(as_uuid=True), nullable=True
    )
    details: Mapped[str] = mapped_column(String(300), nullable=False, default="")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_utcnow
    )
