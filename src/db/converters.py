"""Конвертори між ORM-рядками (Row) та доменними dataclass-об'єктами."""

from typing import Any, TypeVar

from src.db.models import (
    CategoryRow,
    CategorySuggestionRow,
    FavoriteRow,
    ListingImageRow,
    ListingRow,
    ModerationActionRow,
    UserRow,
)
from src.domain.categories import Category
from src.domain.category_suggestions import CategorySuggestion, CategorySuggestionStatus
from src.domain.favorites import Favorite
from src.domain.listings import (
    Listing,
    ListingCondition,
    ListingImage,
    ListingStatus,
)
from src.domain.moderation import ModerationAction, ModerationActionType
from src.domain.users import User, UserRole

RowT = TypeVar("RowT")


def _populate_row(
    row_cls: type[RowT], existing: RowT | None, **attributes: Any
) -> RowT:
    """Утиліта безпечного заповнення атрибутів ORM-рядка.

    Використовує переданий екземпляр `existing` або створює новий об'єкт `row_cls`.
    """
    row = existing or row_cls()
    for attr_name, value in attributes.items():
        setattr(row, attr_name, value)
    return row


# ---------------------------------------------------------------------------
# User
# ---------------------------------------------------------------------------


def user_row_to_domain(row: UserRow) -> User:
    return User(
        user_id=row.user_id,
        tenant_id=row.tenant_id,
        entra_object_id=row.entra_object_id,
        email=row.email,
        display_name=row.display_name,
        role=UserRole(row.role),
        is_blocked=row.is_blocked,
        display_name_customized=row.display_name_customized,
        avatar_url=row.avatar_url,
        contact=row.contact,
        created_at=row.created_at,
    )


def user_domain_to_row(user: User, existing: UserRow | None = None) -> UserRow:
    return _populate_row(
        UserRow,
        existing,
        user_id=user.user_id,
        tenant_id=user.tenant_id,
        entra_object_id=user.entra_object_id,
        email=user.email,
        display_name=user.display_name,
        role=user.role.value,
        is_blocked=user.is_blocked,
        display_name_customized=user.display_name_customized,
        avatar_url=user.avatar_url,
        contact=user.contact,
        created_at=user.created_at,
    )


# ---------------------------------------------------------------------------
# Category
# ---------------------------------------------------------------------------


def category_row_to_domain(row: CategoryRow) -> Category:
    return Category(
        id=row.category_id,
        name=row.name,
        slug=row.slug,
        description=row.description,
        is_active=row.is_active,
        created_at=row.created_at,
    )


def category_domain_to_row(
    cat: Category, existing: CategoryRow | None = None
) -> CategoryRow:
    return _populate_row(
        CategoryRow,
        existing,
        category_id=cat.id,
        name=cat.name,
        slug=cat.slug,
        description=cat.description,
        is_active=cat.is_active,
        created_at=cat.created_at,
    )


# ---------------------------------------------------------------------------
# CategorySuggestion
# ---------------------------------------------------------------------------


def suggestion_row_to_domain(row: CategorySuggestionRow) -> CategorySuggestion:
    return CategorySuggestion(
        suggestion_id=row.suggestion_id,
        name=row.name,
        proposer_id=row.proposer_id,
        status=CategorySuggestionStatus(row.status),
        created_at=row.created_at,
        reviewed_at=row.resolved_at,
    )


def suggestion_domain_to_row(
    s: CategorySuggestion, existing: CategorySuggestionRow | None = None
) -> CategorySuggestionRow:
    return _populate_row(
        CategorySuggestionRow,
        existing,
        suggestion_id=s.suggestion_id,
        name=s.name,
        proposer_id=s.proposer_id,
        status=s.status.value,
        created_at=s.created_at,
        resolved_at=s.reviewed_at,
    )


# ---------------------------------------------------------------------------
# ListingImage
# ---------------------------------------------------------------------------


def image_row_to_domain(row: ListingImageRow) -> ListingImage:
    return ListingImage(
        image_id=row.image_id,
        listing_id=row.listing_id,
        image_url=row.image_url,
        thumbnail_url=row.thumbnail_url,
        storage_key=row.storage_key,
        display_order=row.display_order,
        width=row.width,
        height=row.height,
        thumbnail_width=row.thumbnail_width,
        thumbnail_height=row.thumbnail_height,
    )


def image_domain_to_row(
    img: ListingImage, existing: ListingImageRow | None = None
) -> ListingImageRow:
    return _populate_row(
        ListingImageRow,
        existing,
        image_id=img.image_id,
        listing_id=img.listing_id,
        image_url=img.image_url,
        thumbnail_url=img.thumbnail_url,
        storage_key=img.storage_key,
        display_order=img.display_order,
        width=img.width,
        height=img.height,
        thumbnail_width=img.thumbnail_width,
        thumbnail_height=img.thumbnail_height,
    )


# ---------------------------------------------------------------------------
# Listing
# ---------------------------------------------------------------------------


def listing_row_to_domain(row: ListingRow) -> Listing:
    images = [image_row_to_domain(img) for img in (row.images or [])]
    return Listing(
        id=row.listing_id,
        title=row.title,
        description=row.description,
        price=row.price,
        category_id=row.category_id,
        contact=row.contact,
        user_id=row.user_id,
        condition=ListingCondition(row.condition),
        status=ListingStatus(row.status),
        images=images,
        suggested_category_id=row.suggested_category_id,
        created_at=row.created_at,
        updated_at=row.updated_at,
    )


def listing_domain_to_row(
    listing: Listing, existing: ListingRow | None = None
) -> ListingRow:
    return _populate_row(
        ListingRow,
        existing,
        listing_id=listing.id,
        title=listing.title,
        description=listing.description,
        price=listing.price,
        category_id=listing.category_id,
        contact=listing.contact,
        user_id=listing.user_id,
        condition=listing.condition.value,
        status=listing.status.value,
        suggested_category_id=listing.suggested_category_id,
        created_at=listing.created_at,
        updated_at=listing.updated_at,
    )


# ---------------------------------------------------------------------------
# Favorite
# ---------------------------------------------------------------------------


def favorite_row_to_domain(row: FavoriteRow) -> Favorite:
    return Favorite(
        user_id=row.user_id,
        listing_id=row.listing_id,
        created_at=row.created_at,
    )


def favorite_domain_to_row(
    fav: Favorite, existing: FavoriteRow | None = None
) -> FavoriteRow:
    return _populate_row(
        FavoriteRow,
        existing,
        user_id=fav.user_id,
        listing_id=fav.listing_id,
        created_at=fav.created_at,
    )


# ---------------------------------------------------------------------------
# ModerationAction
# ---------------------------------------------------------------------------


def moderation_row_to_domain(row: ModerationActionRow) -> ModerationAction:
    return ModerationAction(
        id=row.action_id,
        moderator_id=row.moderator_id,
        action_type=ModerationActionType(row.action_type),
        reason=row.reason,
        listing_id=row.listing_id,
        target_user_id=row.target_user_id,
        suggestion_id=row.suggestion_id,
        created_at=row.created_at,
    )


def moderation_domain_to_row(
    action: ModerationAction, existing: ModerationActionRow | None = None
) -> ModerationActionRow:
    return _populate_row(
        ModerationActionRow,
        existing,
        action_id=action.id,
        moderator_id=action.moderator_id,
        action_type=action.action_type.value,
        reason=action.reason,
        listing_id=action.listing_id,
        target_user_id=action.target_user_id,
        suggestion_id=action.suggestion_id,
        created_at=action.created_at,
    )
