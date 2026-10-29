"""Локальна модель користувача, пов'язана з Microsoft Entra ID."""

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from uuid import UUID, uuid4


def utc_now() -> datetime:
    """Повертає поточний UTC-час із часовим поясом."""
    return datetime.now(timezone.utc)


class UserRole(str, Enum):
    """Авторитетні локальні ролі Baraholka NaUKMA."""

    USER = "USER"
    ADMIN = "ADMIN"


@dataclass
class User:
    """Локальний профіль, прив'язаний до стабільної Entra-ідентичності."""

    tenant_id: UUID
    entra_object_id: UUID
    email: str
    display_name: str
    user_id: UUID = field(default_factory=uuid4)
    role: UserRole = UserRole.USER
    is_blocked: bool = False
    display_name_customized: bool = False
    avatar_url: str | None = None
    contact: str | None = None
    created_at: datetime = field(default_factory=utc_now)


@dataclass(frozen=True)
class CurrentUser:
    """Перевірена локальна ідентичність для авторизації backend-операцій."""

    user_id: UUID
    tenant_id: UUID
    entra_object_id: UUID
    email: str
    display_name: str
    role: UserRole
    avatar_url: str | None = None
    contact: str | None = None
