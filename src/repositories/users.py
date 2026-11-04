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

    def get_by_id(self, user_id: UUID) -> User | None:
        """Шукає локального користувача для перевірки сесії."""
        ...

    def get_by_email(self, email: str) -> User | None:
        """Шукає користувача за нормалізованою (casefold) адресою email."""
        ...

    def list_blocked(self) -> list[User]:
        """Повертає заблокованих користувачів від найновішого блокування."""

    def save(self, user: User) -> User:
        """Створює або оновлює локальний профіль."""
        ...


class InMemoryUserRepository:
    """Ізольоване сховище користувачів для модульних тестів."""

    def __init__(self, users: list[User] | None = None) -> None:
        self._users_by_identity: dict[tuple[UUID, UUID], User] = {
            (user.tenant_id, user.entra_object_id): user for user in users or []
        }
        self._users_by_id: dict[UUID, User] = {
            user.user_id: user for user in users or []
        }

    def get_by_entra_identity(
        self, tenant_id: UUID, entra_object_id: UUID
    ) -> User | None:
        return self._users_by_identity.get((tenant_id, entra_object_id))

    def get_by_id(self, user_id: UUID) -> User | None:
        return self._users_by_id.get(user_id)

    def get_by_email(self, email: str) -> User | None:
        wanted = email.strip().casefold()
        for user in self._users_by_id.values():
            if user.email.casefold() == wanted:
                return user
        return None

    def list_blocked(self) -> list[User]:
        blocked = [user for user in self._users_by_id.values() if user.is_blocked]
        blocked.sort(key=lambda user: user.blocked_at or user.created_at, reverse=True)
        return blocked

    def save(self, user: User) -> User:
        self._users_by_identity[(user.tenant_id, user.entra_object_id)] = user
        self._users_by_id[user.user_id] = user
        return user
