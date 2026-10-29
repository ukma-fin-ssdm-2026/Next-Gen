"""Listing Service: каталог, пошук, створення, історія та зміна власних оголошень."""

from collections.abc import Callable
from datetime import datetime, timedelta
from typing import TYPE_CHECKING
from uuid import UUID, uuid4

from src.domain.exceptions import (
    InvalidCategoryError,
    InvalidPriceRangeError,
    ListingForbiddenError,
    ListingNotFoundError,
    ListingUnauthorizedError,
)
from src.domain.listings import (
    OTHER_CATEGORY_ID,
    Listing,
    ListingCondition,
    ListingSortOrder,
    ListingStatus,
    utc_now,
)
from src.domain.users import CurrentUser, User
from src.repositories.favorites import FavoriteRepository
from src.repositories.image_storage import ImageStorage, InMemoryImageStorage
from src.repositories.listings import ListingRepository

if TYPE_CHECKING:
    from src.services.category_suggestions import CategorySuggestionService


class ListingService:
    """Бізнес-правила оголошень незалежно від HTTP-фреймворку."""

    def __init__(
        self,
        repository: ListingRepository,
        image_storage: ImageStorage | None = None,
        favorites: FavoriteRepository | None = None,
        category_validator: Callable[[UUID], bool] | None = None,
        category_suggestion_service: "CategorySuggestionService | None" = None,
    ) -> None:
        self._repository = repository
        self._favorites = favorites
        self._category_validator = category_validator
        self._category_suggestion_service = category_suggestion_service
        self._image_storage: ImageStorage = (
            image_storage if image_storage is not None else InMemoryImageStorage()
        )

    def list_public(
        self,
        skip: int = 0,
        limit: int = 10,
        category_id: UUID | None = None,
        query: str | None = None,
        min_price: float | None = None,
        max_price: float | None = None,
        sort_order: ListingSortOrder = ListingSortOrder.NEWEST,
    ) -> list[Listing]:
        """Каталог активних оголошень (FR-006, FR-007, FR-008)."""
        self._validate_price_range(min_price, max_price)
        items = [item for item in self._repository.list_all() if item.is_public()]
        if category_id is not None:
            items = [item for item in items if item.category_id == category_id]
        if query and query.strip():
            needle = query.strip().casefold()
            items = [
                item
                for item in items
                if needle in item.title.casefold()
                or needle in item.description.casefold()
            ]
        if min_price is not None:
            items = [item for item in items if item.price >= min_price]
        if max_price is not None:
            items = [item for item in items if item.price <= max_price]
        items.sort(
            key=lambda item: item.created_at,
            reverse=sort_order != ListingSortOrder.OLDEST,
        )
        return items[skip : skip + limit]

    def list_owner_listings(
        self, actor_id: UUID | CurrentUser | User | None
    ) -> list[Listing]:
        """Історія активних і знятих оголошень поточного продавця (FR-005)."""
        owner_id = self._require_actor(actor_id)
        items = list(self._repository.list_by_owner(owner_id))
        items.sort(key=lambda item: item.created_at, reverse=True)
        return items

    def get_public(self, listing_id: UUID) -> Listing:
        """Деталі активного оголошення для каталогу. Contact лишається в домені."""
        listing = self._require_listing(listing_id)
        if not listing.is_public():
            raise ListingNotFoundError("Оголошення не знайдено")
        return listing

    def create(
        self,
        actor_id: UUID | CurrentUser | User | None,
        title: str,
        description: str,
        price: float,
        category_id: UUID | None = None,
        contact: str = "",
        condition: ListingCondition = ListingCondition.GOOD,
        image_urls: list[str] | None = None,
        suggested_category_name: str | None = None,
    ) -> Listing:
        """Створює оголошення від імені актора з фотографіями (FR-002, FR-015)."""
        owner_id = self._require_actor(actor_id)
        target_category_id = (
            OTHER_CATEGORY_ID if suggested_category_name is not None else category_id
        )
        if target_category_id is None:
            raise InvalidCategoryError(
                "Потрібно вказати category_id або suggested_category_name"
            )
        if self._category_validator is not None and not self._category_validator(
            target_category_id
        ):
            raise InvalidCategoryError(
                f"Категорія {target_category_id} не існує або була деактивована"
            )

        suggestion_id: UUID | None = None
        if suggested_category_name is not None:
            if self._category_suggestion_service is None:
                raise InvalidCategoryError("Сервіс пропозицій категорій не налаштовано")
            suggestion = self._category_suggestion_service.submit(
                actor_id, suggested_category_name
            )
            suggestion_id = suggestion.suggestion_id

        listing_id = uuid4()
        try:
            images = self._image_storage.save_images(
                listing_id,
                image_urls if image_urls is not None else [],
                actor_id=owner_id,
            )
            listing = Listing(
                id=listing_id,
                title=title,
                description=description,
                price=price,
                category_id=target_category_id,
                contact=contact,
                user_id=owner_id,
                condition=condition,
                status=ListingStatus.ACTIVE,
                images=images,
                suggested_category_id=suggestion_id,
            )
            return self._repository.add(listing)
        except Exception:
            if (
                suggestion_id is not None
                and self._category_suggestion_service is not None
            ):
                self._category_suggestion_service.delete(suggestion_id)
            raise

    def get_suggested_category_name(self, listing: Listing) -> str | None:
        """Повертає назву запропонованої категорії для власника оголошення (FR-015)."""
        if (
            listing.suggested_category_id is None
            or self._category_suggestion_service is None
        ):
            return None
        suggestion = self._category_suggestion_service.get(
            listing.suggested_category_id
        )
        return suggestion.name if suggestion is not None else None

    def update(
        self,
        listing_id: UUID,
        actor_id: UUID | CurrentUser | User | None,
        title: str | None = None,
        description: str | None = None,
        price: float | None = None,
        contact: str | None = None,
        condition: ListingCondition | None = None,
        image_urls: list[str] | None = None,
    ) -> Listing:
        """Оновлює лише власне оголошення атомарно (FR-003, TM-02)."""
        listing = self._require_owned(listing_id, actor_id)
        new_images = (
            self._image_storage.save_images(
                listing.id, image_urls, actor_id=listing.user_id
            )
            if image_urls is not None
            else None
        )
        if title is not None:
            listing.title = title
        if description is not None:
            listing.description = description
        if price is not None:
            listing.price = price
        if contact is not None:
            listing.contact = contact
        if condition is not None:
            listing.condition = condition
        if new_images is not None:
            listing.images = new_images
        listing.updated_at = self._next_timestamp(listing.updated_at)
        return self._repository.save(listing)

    def delete(
        self, listing_id: UUID, actor_id: UUID | CurrentUser | User | None
    ) -> Listing:
        """Знімає оголошення з публікації (WITHDRAWN, FR-004).

        Зняте оголошення одразу прибирається з обраного всіх користувачів (FR-009).
        """
        listing = self._require_owned(listing_id, actor_id)
        listing.status = ListingStatus.WITHDRAWN
        listing.updated_at = self._next_timestamp(listing.updated_at)
        saved = self._repository.save(listing)
        if self._favorites is not None:
            self._favorites.delete_by_listing(listing.id)
        return saved

    def _require_listing(self, listing_id: UUID) -> Listing:
        listing = self._repository.get(listing_id)
        if listing is None:
            raise ListingNotFoundError("Оголошення не знайдено")
        return listing

    def _require_actor(self, actor_id: UUID | CurrentUser | User | None) -> UUID:
        if actor_id is None:
            raise ListingUnauthorizedError("Потрібна ідентифікація користувача")
        if isinstance(actor_id, (CurrentUser, User)):
            if getattr(actor_id, "is_blocked", False):
                raise ListingForbiddenError(
                    "Заблокований користувач не може змінювати оголошення"
                )
            return actor_id.user_id
        return actor_id

    def _require_owned(
        self, listing_id: UUID, actor_id: UUID | CurrentUser | User | None
    ) -> Listing:
        owner_id = self._require_actor(actor_id)
        listing = self._require_listing(listing_id)
        if listing.user_id != owner_id:
            raise ListingForbiddenError("Немає прав змінювати чуже оголошення")
        return listing

    @staticmethod
    def _next_timestamp(previous: datetime) -> datetime:
        now = utc_now()
        return now if now > previous else previous + timedelta(microseconds=1)

    @staticmethod
    def _validate_price_range(min_price: float | None, max_price: float | None) -> None:
        if min_price is not None and max_price is not None and min_price > max_price:
            raise InvalidPriceRangeError(
                f"min_price ({min_price}) не може перевищувати max_price ({max_price})"
            )
