"""Репозиторій оголошень. Інтерфейс не залежить від FastAPI."""

from typing import Protocol
from uuid import UUID

from src.domain.listings import Listing, build_seed_listings


class ListingRepository(Protocol):
    """Контракт сховища оголошень для Listing Service."""

    def list_all(self) -> list[Listing]:
        """Повертає всі оголошення, включно зі знятими з публікації."""

    def get(self, listing_id: UUID) -> Listing | None:
        """Повертає оголошення за id або None."""

    def add(self, listing: Listing) -> Listing:
        """Зберігає нове оголошення."""

    def save(self, listing: Listing) -> Listing:
        """Оновлює наявне оголошення."""

    def delete(self, listing_id: UUID) -> bool:
        """Видаляє оголошення. True, якщо запис існував."""


class InMemoryListingRepository:
    """Прототипне сховище в пам'яті процесу (до підключення PostgreSQL)."""

    def __init__(self, items: list[Listing] | None = None) -> None:
        self._items: dict[UUID, Listing] = {item.id: item for item in items or []}

    @classmethod
    def with_seed(cls) -> "InMemoryListingRepository":
        """Створює репозиторій із демонстраційними оголошеннями."""
        return cls(build_seed_listings())

    def list_all(self) -> list[Listing]:
        return list(self._items.values())

    def get(self, listing_id: UUID) -> Listing | None:
        return self._items.get(listing_id)

    def add(self, listing: Listing) -> Listing:
        self._items[listing.id] = listing
        return listing

    def save(self, listing: Listing) -> Listing:
        self._items[listing.id] = listing
        return listing

    def delete(self, listing_id: UUID) -> bool:
        return self._items.pop(listing_id, None) is not None
