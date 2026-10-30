"""PostgreSQL-адаптери для Favorites та ModerationAction (ADR-002)."""

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from src.db.converters import (
    favorite_domain_to_row,
    favorite_row_to_domain,
    moderation_domain_to_row,
    moderation_row_to_domain,
)
from src.db.models import FavoriteRow, ModerationActionRow
from src.domain.favorites import Favorite
from src.domain.moderation import ModerationAction

# ---------------------------------------------------------------------------
# Favorites
# ---------------------------------------------------------------------------


class PostgresFavoriteRepository:
    """Реалізує FavoriteRepository.Protocol, зберігаючи дані у PostgreSQL."""

    def __init__(self, session: Session) -> None:
        self._session = session

    def get(self, user_id: UUID, listing_id: UUID) -> Favorite | None:
        row = self._session.get(FavoriteRow, (user_id, listing_id))
        return favorite_row_to_domain(row) if row else None

    def add(self, favorite: Favorite) -> Favorite:
        row = favorite_domain_to_row(favorite)
        self._session.add(row)
        self._session.flush()
        return favorite_row_to_domain(row)

    def list_by_user(self, user_id: UUID) -> list[Favorite]:
        stmt = (
            select(FavoriteRow)
            .where(FavoriteRow.user_id == user_id)
            .order_by(FavoriteRow.created_at.desc())
        )
        rows = self._session.execute(stmt).scalars().all()
        return [favorite_row_to_domain(r) for r in rows]

    def delete(self, user_id: UUID, listing_id: UUID) -> bool:
        row = self._session.get(FavoriteRow, (user_id, listing_id))
        if row is None:
            return False
        self._session.delete(row)
        self._session.flush()
        return True

    def list_by_listing(self, listing_id: UUID) -> list[Favorite]:
        stmt = select(FavoriteRow).where(FavoriteRow.listing_id == listing_id)
        rows = self._session.execute(stmt).scalars().all()
        return [favorite_row_to_domain(r) for r in rows]

    def delete_by_listing(self, listing_id: UUID) -> int:
        stmt = select(FavoriteRow).where(FavoriteRow.listing_id == listing_id)
        rows = self._session.execute(stmt).scalars().all()
        count = len(rows)
        for row in rows:
            self._session.delete(row)
        if count:
            self._session.flush()
        return count


# ---------------------------------------------------------------------------
# ModerationAction
# ---------------------------------------------------------------------------


class PostgresModerationActionRepository:
    """Реалізує ModerationActionRepository.Protocol, зберігаючи дані у PostgreSQL.

    Append-only: рядки не оновлюються та не видаляються (FR-011).
    Зміна статусу оголошення та додавання ModerationAction повинні виконуватись
    в одній транзакції — це відповідальність сервісного рівня.
    """

    def __init__(self, session: Session) -> None:
        self._session = session

    def add(self, action: ModerationAction) -> ModerationAction:
        row = moderation_domain_to_row(action)
        self._session.add(row)
        self._session.flush()
        return moderation_row_to_domain(row)

    def list_by_listing(self, listing_id: UUID) -> list[ModerationAction]:
        stmt = (
            select(ModerationActionRow)
            .where(ModerationActionRow.listing_id == listing_id)
            .order_by(ModerationActionRow.created_at)
        )
        rows = self._session.execute(stmt).scalars().all()
        return [moderation_row_to_domain(r) for r in rows]

    def list_by_user(self, user_id: UUID) -> list[ModerationAction]:
        stmt = (
            select(ModerationActionRow)
            .where(ModerationActionRow.target_user_id == user_id)
            .order_by(ModerationActionRow.created_at)
        )
        rows = self._session.execute(stmt).scalars().all()
        return [moderation_row_to_domain(r) for r in rows]

    def list_by_suggestion(self, suggestion_id: UUID) -> list[ModerationAction]:
        stmt = (
            select(ModerationActionRow)
            .where(ModerationActionRow.suggestion_id == suggestion_id)
            .order_by(ModerationActionRow.created_at)
        )
        rows = self._session.execute(stmt).scalars().all()
        return [moderation_row_to_domain(r) for r in rows]

    def list_all(self) -> list[ModerationAction]:
        stmt = select(ModerationActionRow).order_by(ModerationActionRow.created_at)
        rows = self._session.execute(stmt).scalars().all()
        return [moderation_row_to_domain(r) for r in rows]
