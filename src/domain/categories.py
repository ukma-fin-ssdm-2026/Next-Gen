"""Сутність категорії оголошень (FR-012)."""

from dataclasses import dataclass, field
from datetime import datetime
from uuid import UUID, uuid4

from src.domain.exceptions import InvalidCategoryError
from src.domain.listings import utc_now


@dataclass
class Category:
    """Категорія каталогу оголошень.

    Кожна категорія має унікальний системний id та людинозрозумілий slug.
    Деактивовані категорії (is_active=False) зберігаються в сховищі для забезпечення
    цілісності зв'язків із наявними оголошеннями, але виключаються з публічного переліку
    доступних для нових оголошень (FR-012).
    """

    id: UUID
    name: str
    slug: str
    description: str | None = None
    is_active: bool = True
    created_at: datetime = field(default_factory=utc_now)

    @classmethod
    def create(
        cls,
        name: str,
        slug: str,
        description: str | None = None,
        category_id: UUID | None = None,
    ) -> "Category":
        """Фабричний метод створення категорії з валідацією полів."""
        clean_name = name.strip()
        if not clean_name:
            raise InvalidCategoryError("Назва категорії не може бути порожньою")

        clean_slug = slug.strip().lower()
        if not clean_slug:
            raise InvalidCategoryError("Slug категорії не може бути порожнім")

        clean_desc = description.strip() if description else None

        return cls(
            id=category_id or uuid4(),
            name=clean_name,
            slug=clean_slug,
            description=clean_desc,
            is_active=True,
            created_at=utc_now(),
        )
