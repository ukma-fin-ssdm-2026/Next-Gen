"""Контракт і in-memory адаптер сховища користувачів."""

from typing import Protocol
from uuid import UUID

from src.domain.users import User


class UserRepository(Protocol):
    """Контракт локальних профілів, пов'язаних з Entra ID."""

    def get_by_entra_identity(
        self, tenant_id: UUID, entra_object_id: UUID
    ) -> User | None:
        """Шукає користувача за стабільною парою tenant ID та object ID."""
        ...

    def save(self, user: User) -> User:
        """Створює або оновлює локальний профіль."""
        ...


class InMemoryUserRepository:
    """Ізольоване сховище користувачів для модульних тестів."""

    def __init__(self, users: list[User] | None = None) -> None:
        self._users: dict[tuple[UUID, UUID], User] = {
            (user.tenant_id, user.entra_object_id): user for user in users or []
        }

    def get_by_entra_identity(
        self, tenant_id: UUID, entra_object_id: UUID
    ) -> User | None:
        return self._users.get((tenant_id, entra_object_id))

    def save(self, user: User) -> User:
        self._users[(user.tenant_id, user.entra_object_id)] = user
        return user
