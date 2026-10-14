"""Listing Service: каталог, пошук, створення та зміна власних оголошень."""

from uuid import UUID

from src.domain.exceptions import (
    ListingForbiddenError,
    ListingNotFoundError,
    ListingUnauthorizedError,
)
from src.domain.listings import Listing, ListingStatus, utc_now
from src.repositories.listings import ListingRepository


class ListingService:
    """Бізнес-правила оголошень незалежно від HTTP-фреймворку."""

    def __init__(self, repository: ListingRepository) -> None:
        self._repository = repository

    def list_public(
        self,
        skip: int = 0,
        limit: int = 10,
        category_id: UUID | None = None,
        query: str | None = None,
    ) -> list[Listing]:
        """Каталог активних оголошень (FR-006, FR-007, FR-008)."""
        items = [item for item in self._repository.list_all() if item.is_public()]
        if category_id is not None:
            items = [item for item in items if item.category_id == category_id]
        if query:
            needle = query.casefold()
            items = [
                item
                for item in items
                if needle in item.title.casefold()
                or needle in item.description.casefold()
            ]
        items.sort(key=lambda item: item.created_at, reverse=True)
        return items[skip : skip + limit]

    def get_public(self, listing_id: UUID) -> Listing:
        """Деталі активного оголошення для каталогу. Contact лишається в домені."""
        listing = self._require_listing(listing_id)
        if not listing.is_public():
            raise ListingNotFoundError("Оголошення не знайдено")
        return listing

    def create(
        self,
        actor_id: UUID | None,
        title: str,
        description: str,
        price: float,
        category_id: UUID,
        contact: str,
    ) -> Listing:
        """Створює оголошення від імені актора. user_id з тіла запиту ігнорується."""
        owner_id = self._require_actor(actor_id)
        listing = Listing(
            title=title,
            description=description,
            price=price,
            category_id=category_id,
            contact=contact,
            user_id=owner_id,
            status=ListingStatus.ACTIVE,
        )
        return self._repository.add(listing)

    def update(
        self,
        listing_id: UUID,
        actor_id: UUID | None,
        title: str | None = None,
        description: str | None = None,
        price: float | None = None,
        contact: str | None = None,
    ) -> Listing:
        """Оновлює лише власне оголошення (FR-003, TM-02)."""
        listing = self._require_owned(listing_id, actor_id)
        if title is not None:
            listing.title = title
        if description is not None:
            listing.description = description
        if price is not None:
            listing.price = price
        if contact is not None:
            listing.contact = contact
        listing.updated_at = utc_now()
        return self._repository.save(listing)

    def delete(self, listing_id: UUID, actor_id: UUID | None) -> None:
        """Видаляє лише власне оголошення."""
        self._require_owned(listing_id, actor_id)
        self._repository.delete(listing_id)

    def _require_listing(self, listing_id: UUID) -> Listing:
        listing = self._repository.get(listing_id)
        if listing is None:
            raise ListingNotFoundError("Оголошення не знайдено")
        return listing

    def _require_actor(self, actor_id: UUID | None) -> UUID:
        if actor_id is None:
            raise ListingUnauthorizedError("Потрібна ідентифікація користувача")
        return actor_id

    def _require_owned(self, listing_id: UUID, actor_id: UUID | None) -> Listing:
        owner_id = self._require_actor(actor_id)
        listing = self._require_listing(listing_id)
        if listing.user_id != owner_id:
            raise ListingForbiddenError("Немає прав змінювати чуже оголошення")
        return listing
