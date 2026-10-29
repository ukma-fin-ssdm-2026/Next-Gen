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
