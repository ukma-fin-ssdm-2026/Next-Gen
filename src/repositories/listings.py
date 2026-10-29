"""Репозиторій оголошень. Інтерфейс не залежить від FastAPI."""

from threading import RLock
from typing import Protocol
from uuid import UUID

from src.domain.listings import Listing, build_seed_listings


class ListingRepository(Protocol):
    """Контракт сховища оголошень для Listing Service."""

    def list_all(self) -> list[Listing]:
        """Повертає всі оголошення, включно зі знятими з публікації."""

    def list_by_owner(self, user_id: UUID) -> list[Listing]:
        """Повертає всі оголошення вказаного продавця (активні та зняті, FR-005)."""

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
        self._mutation_lock = RLock()

    @classmethod
    def with_seed(cls) -> "InMemoryListingRepository":
        """Створює репозиторій із демонстраційними оголошеннями."""
        return cls(build_seed_listings())

    def list_all(self) -> list[Listing]:
        return list(self._items.values())

    def list_by_owner(self, user_id: UUID) -> list[Listing]:
        return [item for item in self._items.values() if item.user_id == user_id]

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


def get_listing_mutation_lock(repository: ListingRepository) -> RLock:
    """Повертає спільний RLock для серіалізації змін оголошень у межах репозиторію."""
    lock = getattr(repository, "_mutation_lock", None)
    if isinstance(lock, type(RLock())):
        return lock
    new_lock = RLock()
    try:
        setattr(repository, "_mutation_lock", new_lock)
    except Exception:
        return new_lock
    return new_lock
