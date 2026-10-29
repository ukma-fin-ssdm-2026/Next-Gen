"""Журнал дій модерації. Інтерфейс не залежить від FastAPI і конкретної БД."""

from typing import Protocol
from uuid import UUID

from src.domain.moderation import ModerationAction


class ModerationActionRepository(Protocol):
    """Контракт append-only сховища дій модерації (без update/delete)."""

    def add(self, action: ModerationAction) -> ModerationAction:
        """Зберігає новий запис дії модерації."""

    def list_by_listing(self, listing_id: UUID) -> list[ModerationAction]:
        """Повертає історію модерації оголошення від найдавнішої дії."""

    def list_by_user(self, user_id: UUID) -> list[ModerationAction]:
        """Повертає історію модерації користувача від найдавнішої дії."""

    def list_by_suggestion(self, suggestion_id: UUID) -> list[ModerationAction]:
        """Повертає історію модерації пропозиції категорії."""

    def list_all(self) -> list[ModerationAction]:
        """Повертає всі записи модерації."""


class InMemoryModerationActionRepository:
    """Прототипний журнал модерації в пам'яті процесу (до підключення PostgreSQL)."""

    def __init__(self) -> None:
        self._items: list[ModerationAction] = []

    def add(self, action: ModerationAction) -> ModerationAction:
        self._items.append(action)
        return action

    def list_by_listing(self, listing_id: UUID) -> list[ModerationAction]:
        return [item for item in self._items if item.listing_id == listing_id]

    def list_by_user(self, user_id: UUID) -> list[ModerationAction]:
        return [item for item in self._items if item.target_user_id == user_id]

    def list_by_suggestion(self, suggestion_id: UUID) -> list[ModerationAction]:
        return [item for item in self._items if item.suggestion_id == suggestion_id]

    def list_all(self) -> list[ModerationAction]:
        return list(self._items)
