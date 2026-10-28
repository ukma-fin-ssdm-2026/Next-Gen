"""Seller Contact Service: контакт продавця для автентифікованого покупця.

FR-010, SEC-002. Публічні схеми каталогу, деталей і обраного контакт не містять;
єдине місце, де він віддається назовні, — цей сценарій після перевірки сесії.
"""

from dataclasses import dataclass
from uuid import UUID

from src.domain.exceptions import ListingNotFoundError, ListingUnauthorizedError
from src.repositories.listings import ListingRepository


@dataclass(frozen=True)
class SellerContact:
    """Контакт продавця конкретного активного оголошення."""

    listing_id: UUID
    contact: str


class SellerContactService:
    """Бізнес-правила доступу до контакту незалежно від HTTP-фреймворку."""

    def __init__(self, listings: ListingRepository) -> None:
        self._listings = listings

    def get_contact(self, viewer_id: UUID | None, listing_id: UUID) -> SellerContact:
        """Повертає контакт лише ідентифікованому користувачу й лише для ACTIVE."""
        if viewer_id is None:
            raise ListingUnauthorizedError("Потрібна ідентифікація користувача")
        listing = self._listings.get(listing_id)
        if listing is None or not listing.is_public():
            raise ListingNotFoundError("Оголошення не знайдено")
        return SellerContact(listing_id=listing.id, contact=listing.contact)
