"""Репозиторій пропозицій нових категорій (FR-015 / US-010)."""

from typing import Protocol
from uuid import UUID

from src.domain.category_suggestions import (
    CategorySuggestion,
    CategorySuggestionStatus,
)


class CategorySuggestionRepository(Protocol):
    """Інтерфейс сховища пропозицій категорій."""

    def get(self, suggestion_id: UUID) -> CategorySuggestion | None: ...

    def list_all(self) -> list[CategorySuggestion]: ...

    def list_by_status(
        self, status: CategorySuggestionStatus
    ) -> list[CategorySuggestion]: ...

    def list_by_proposer(
        self,
        proposer_id: UUID,
        status: CategorySuggestionStatus | None = None,
    ) -> list[CategorySuggestion]: ...

    def find_pending_by_name(self, name: str) -> CategorySuggestion | None: ...

    def add(self, suggestion: CategorySuggestion) -> CategorySuggestion: ...

    def save(self, suggestion: CategorySuggestion) -> CategorySuggestion: ...

    def delete(self, suggestion_id: UUID) -> bool: ...


class InMemoryCategorySuggestionRepository:
    """In-memory реалізація сховища пропозицій категорій."""

    def __init__(self) -> None:
        self._items: dict[UUID, CategorySuggestion] = {}

    def get(self, suggestion_id: UUID) -> CategorySuggestion | None:
        return self._items.get(suggestion_id)

    def list_all(self) -> list[CategorySuggestion]:
        return list(self._items.values())

    def list_by_status(
        self, status: CategorySuggestionStatus
    ) -> list[CategorySuggestion]:
        return [item for item in self._items.values() if item.status == status]

    def list_by_proposer(
        self,
        proposer_id: UUID,
        status: CategorySuggestionStatus | None = None,
    ) -> list[CategorySuggestion]:
        return [
            item
            for item in self._items.values()
            if item.proposer_id == proposer_id
            and (status is None or item.status == status)
        ]

    def find_pending_by_name(self, name: str) -> CategorySuggestion | None:
        key = name.strip().casefold()
        for item in self._items.values():
            if (
                item.status == CategorySuggestionStatus.PENDING
                and item.name.strip().casefold() == key
            ):
                return item
        return None

    def add(self, suggestion: CategorySuggestion) -> CategorySuggestion:
        self._items[suggestion.suggestion_id] = suggestion
        return suggestion

    def save(self, suggestion: CategorySuggestion) -> CategorySuggestion:
        self._items[suggestion.suggestion_id] = suggestion
        return suggestion

    def delete(self, suggestion_id: UUID) -> bool:
        return self._items.pop(suggestion_id, None) is not None
