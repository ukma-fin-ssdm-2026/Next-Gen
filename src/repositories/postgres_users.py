"""PostgreSQL-адаптер репозиторію користувачів (ADR-002)."""

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from src.db.converters import user_domain_to_row, user_row_to_domain
from src.db.models import UserRow
from src.domain.users import User


class PostgresUserRepository:
    """Реалізує UserRepository.Protocol, зберігаючи дані у PostgreSQL."""

    def __init__(self, session: Session) -> None:
        self._session = session

    def get_by_entra_identity(
        self, tenant_id: UUID, entra_object_id: UUID
    ) -> User | None:
        """Шукає користувача за стабільною парою tenant ID та object ID."""
        stmt = select(UserRow).where(
            UserRow.tenant_id == tenant_id,
            UserRow.entra_object_id == entra_object_id,
        )
        row = self._session.execute(stmt).scalar_one_or_none()
        return user_row_to_domain(row) if row else None

    def get_by_id(self, user_id: UUID) -> User | None:
        """Шукає локального користувача для перевірки сесії."""
        row = self._session.get(UserRow, user_id)
        return user_row_to_domain(row) if row else None

    def get_by_email(self, email: str) -> User | None:
        """Шукає користувача за нормалізованою (casefold) адресою email."""
        normalized = email.strip().casefold()
        stmt = select(UserRow).where(UserRow.email == normalized)
        row = self._session.execute(stmt).scalar_one_or_none()
        return user_row_to_domain(row) if row else None

    def list_blocked(self) -> list[User]:
        """Повертає заблокованих користувачів від найновішого блокування."""
        stmt = (
            select(UserRow)
            .where(UserRow.is_blocked.is_(True))
            .order_by(UserRow.blocked_at.desc().nulls_last())
        )
        return [user_row_to_domain(r) for r in self._session.execute(stmt).scalars()]

    def save(self, user: User) -> User:
        """Створює або оновлює локальний профіль.

        Використовується merge, щоб уникнути дублювання при паралельних запитах.
        """
        existing = self._session.get(UserRow, user.user_id)
        row = user_domain_to_row(user, existing)
        if existing is None:
            self._session.add(row)
        self._session.flush()
        return user_row_to_domain(row)
