"""PostgreSQL-адаптер репозиторію категорій (ADR-002, FR-012)."""

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from src.db.converters import category_domain_to_row, category_row_to_domain
from src.db.models import CategoryRow
from src.domain.categories import Category
from src.domain.exceptions import CategoryNotFoundError, DuplicateCategoryError


class PostgresCategoryRepository:
    """Реалізує CategoryRepository.Protocol, зберігаючи дані у PostgreSQL."""

    def __init__(self, session: Session) -> None:
        self._session = session

    def get(self, category_id: UUID) -> Category | None:
        row = self._session.get(CategoryRow, category_id)
        return category_row_to_domain(row) if row else None

    def get_by_slug(self, slug: str) -> Category | None:
        stmt = select(CategoryRow).where(CategoryRow.slug == slug.strip().lower())
        row = self._session.execute(stmt).scalar_one_or_none()
        return category_row_to_domain(row) if row else None

    def get_by_name(self, name: str) -> Category | None:
        stmt = select(CategoryRow).where(CategoryRow.name == name.strip())
        row = self._session.execute(stmt).scalar_one_or_none()
        return category_row_to_domain(row) if row else None

    def list_all(self) -> list[Category]:
        stmt = select(CategoryRow).order_by(CategoryRow.name)
        rows = self._session.execute(stmt).scalars().all()
        return [category_row_to_domain(r) for r in rows]

    def list_active(self) -> list[Category]:
        stmt = (
            select(CategoryRow)
            .where(CategoryRow.is_active.is_(True))
            .order_by(CategoryRow.name)
        )
        rows = self._session.execute(stmt).scalars().all()
        return [category_row_to_domain(r) for r in rows]

    def add(self, category: Category) -> Category:
        existing = self._session.get(CategoryRow, category.id)
        if existing:
            raise DuplicateCategoryError(f"Категорія з id {category.id} вже існує")
        row = category_domain_to_row(category)
        self._session.add(row)
        try:
            self._session.flush()
        except IntegrityError as exc:
            self._session.rollback()
            raise DuplicateCategoryError(
                "Категорія з такою назвою або slug вже існує"
            ) from exc
        return category_row_to_domain(row)

    def update(self, category: Category) -> Category:
        existing = self._session.get(CategoryRow, category.id)
        if existing is None:
            raise CategoryNotFoundError(f"Категорія {category.id} не знайдена")
        row = category_domain_to_row(category, existing)
        try:
            self._session.flush()
        except IntegrityError as exc:
            self._session.rollback()
            raise DuplicateCategoryError(
                "Категорія з такою назвою або slug вже існує"
            ) from exc
        return category_row_to_domain(row)
