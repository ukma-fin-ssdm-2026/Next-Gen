"""Favorite Service: обране покупця (FR-009)."""

from uuid import UUID

from src.domain.exceptions import (
    FavoriteNotFoundError,
    ListingNotFoundError,
    ListingUnauthorizedError,
)
from src.domain.favorites import Favorite
from src.domain.listings import Listing
from src.repositories.favorites import FavoriteRepository
from src.repositories.listings import ListingRepository


class FavoriteService:
    """Бізнес-правила обраного незалежно від HTTP-фреймворку."""

    def __init__(
        self, favorites: FavoriteRepository, listings: ListingRepository
    ) -> None:
        self._favorites = favorites
        self._listings = listings

    def add(self, actor_id: UUID | None, listing_id: UUID) -> Favorite:
        """Додає активне оголошення в обране. Повторне додавання не дублює запис."""
        user_id = self._require_actor(actor_id)
        listing = self._listings.get(listing_id)
        if listing is None or not listing.is_public():
            raise ListingNotFoundError("Оголошення не знайдено")
        existing = self._favorites.get(user_id, listing_id)
        if existing is not None:
            return existing
        return self._favorites.add(Favorite(user_id=user_id, listing_id=listing_id))

    def list_for(self, actor_id: UUID | None) -> list[Listing]:
        """Обране користувача: лише активні оголошення, спершу додані останніми."""
        user_id = self._require_actor(actor_id)
        favorites = sorted(
            self._favorites.list_by_user(user_id),
            key=lambda item: item.created_at,
            reverse=True,
        )
        result = []
        for favorite in favorites:
            listing = self._listings.get(favorite.listing_id)
            if listing is not None and listing.is_public():
                result.append(listing)
        return result

    def remove(self, actor_id: UUID | None, listing_id: UUID) -> None:
        """Прибирає оголошення з власного обраного."""
        user_id = self._require_actor(actor_id)
        if not self._favorites.delete(user_id, listing_id):
            raise FavoriteNotFoundError("Оголошення немає в обраному")

    def _require_actor(self, actor_id: UUID | None) -> UUID:
        if actor_id is None:
            raise ListingUnauthorizedError("Потрібна ідентифікація користувача")
        return actor_id
