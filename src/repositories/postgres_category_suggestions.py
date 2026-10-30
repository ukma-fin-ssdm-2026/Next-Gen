"""PostgreSQL-адаптер репозиторію пропозицій категорій (FR-015)."""

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from src.db.converters import suggestion_domain_to_row, suggestion_row_to_domain
from src.db.models import CategorySuggestionRow
from src.domain.category_suggestions import CategorySuggestion, CategorySuggestionStatus


class PostgresCategorySuggestionRepository:
    """Реалізує CategorySuggestionRepository.Protocol, зберігаючи дані у PostgreSQL."""

    def __init__(self, session: Session) -> None:
        self._session = session

    def get(self, suggestion_id: UUID) -> CategorySuggestion | None:
        row = self._session.get(CategorySuggestionRow, suggestion_id)
        return suggestion_row_to_domain(row) if row else None

    def list_all(self) -> list[CategorySuggestion]:
        stmt = select(CategorySuggestionRow).order_by(
            CategorySuggestionRow.created_at.desc()
        )
        rows = self._session.execute(stmt).scalars().all()
        return [suggestion_row_to_domain(r) for r in rows]

    def list_by_status(
        self, status: CategorySuggestionStatus
    ) -> list[CategorySuggestion]:
        stmt = (
            select(CategorySuggestionRow)
            .where(CategorySuggestionRow.status == status.value)
            .order_by(CategorySuggestionRow.created_at.desc())
        )
        rows = self._session.execute(stmt).scalars().all()
        return [suggestion_row_to_domain(r) for r in rows]

    def list_by_proposer(
        self,
        proposer_id: UUID,
        status: CategorySuggestionStatus | None = None,
    ) -> list[CategorySuggestion]:
        stmt = select(CategorySuggestionRow).where(
            CategorySuggestionRow.proposer_id == proposer_id
        )
        if status is not None:
            stmt = stmt.where(CategorySuggestionRow.status == status.value)
        stmt = stmt.order_by(CategorySuggestionRow.created_at.desc())
        rows = self._session.execute(stmt).scalars().all()
        return [suggestion_row_to_domain(r) for r in rows]

    def find_pending_by_name(self, name: str) -> CategorySuggestion | None:
        key = name.strip().casefold()
        stmt = select(CategorySuggestionRow).where(
            CategorySuggestionRow.status == CategorySuggestionStatus.PENDING.value
        )
        rows = self._session.execute(stmt).scalars().all()
        for row in rows:
            if row.name.strip().casefold() == key:
                return suggestion_row_to_domain(row)
        return None

    def add(self, suggestion: CategorySuggestion) -> CategorySuggestion:
        row = suggestion_domain_to_row(suggestion)
        self._session.add(row)
        self._session.flush()
        return suggestion_row_to_domain(row)

    def save(self, suggestion: CategorySuggestion) -> CategorySuggestion:
        existing = self._session.get(CategorySuggestionRow, suggestion.suggestion_id)
        row = suggestion_domain_to_row(suggestion, existing)
        if existing is None:
            self._session.add(row)
        self._session.flush()
        return suggestion_row_to_domain(row)

    def delete(self, suggestion_id: UUID) -> bool:
        row = self._session.get(CategorySuggestionRow, suggestion_id)
        if row is None:
            return False
        self._session.delete(row)
        self._session.flush()
        return True
