"""Репозиторій обраного. Інтерфейс не залежить від FastAPI."""

from typing import Protocol
from uuid import UUID

from src.domain.favorites import Favorite


class FavoriteRepository(Protocol):
    """Контракт сховища обраного для Favorite Service."""

    def get(self, user_id: UUID, listing_id: UUID) -> Favorite | None:
        """Повертає запис обраного або None."""

    def add(self, favorite: Favorite) -> Favorite:
        """Зберігає новий запис обраного."""

    def list_by_user(self, user_id: UUID) -> list[Favorite]:
        """Повертає всі записи обраного користувача."""

    def delete(self, user_id: UUID, listing_id: UUID) -> bool:
        """Видаляє запис. True, якщо запис існував."""

    def list_by_listing(self, listing_id: UUID) -> list[Favorite]:
        """Повертає всі записи обраного з цим оголошенням (для відкату модерації)."""

    def delete_by_listing(self, listing_id: UUID) -> int:
        """Прибирає оголошення з обраного всіх користувачів. Повертає кількість."""


class InMemoryFavoriteRepository:
    """Прототипне сховище обраного в пам'яті процесу (до підключення PostgreSQL)."""

    def __init__(self, items: list[Favorite] | None = None) -> None:
        self._items: dict[tuple[UUID, UUID], Favorite] = {
            (item.user_id, item.listing_id): item for item in items or []
        }

    def get(self, user_id: UUID, listing_id: UUID) -> Favorite | None:
        return self._items.get((user_id, listing_id))

    def add(self, favorite: Favorite) -> Favorite:
        self._items[(favorite.user_id, favorite.listing_id)] = favorite
        return favorite

    def list_by_user(self, user_id: UUID) -> list[Favorite]:
        return [item for item in self._items.values() if item.user_id == user_id]

    def delete(self, user_id: UUID, listing_id: UUID) -> bool:
        return self._items.pop((user_id, listing_id), None) is not None

    def list_by_listing(self, listing_id: UUID) -> list[Favorite]:
        return [item for item in self._items.values() if item.listing_id == listing_id]

    def delete_by_listing(self, listing_id: UUID) -> int:
        keys = [key for key in self._items if key[1] == listing_id]
        for key in keys:
            del self._items[key]
        return len(keys)
