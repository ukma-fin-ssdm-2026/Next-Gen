"""Category Service: бізнес-логіка керування категоріями (FR-012)."""

from uuid import UUID

from src.domain.categories import Category
from src.domain.exceptions import CategoryNotFoundError, InvalidCategoryError
from src.repositories.categories import CategoryRepository


class CategoryService:
    """Сервісний шар для роботи з категоріями оголошень."""

    def __init__(self, repository: CategoryRepository) -> None:
        self._repository = repository

    def list_active(self) -> list[Category]:
        """Повертає список усіх активних категорій, відсортованих за назвою."""
        active = self._repository.list_active()
        return sorted(active, key=lambda cat: cat.name)

    def get_by_id(self, category_id: UUID) -> Category:
        """Повертає категорію за її ID або збуджує CategoryNotFoundError."""
        category = self._repository.get(category_id)
        if category is None:
            raise CategoryNotFoundError(f"Категорію {category_id} не знайдено")
        return category

    def get_by_slug(self, slug: str) -> Category:
        """Повертає категорію за її slug або збуджує CategoryNotFoundError."""
        category = self._repository.get_by_slug(slug)
        if category is None:
            raise CategoryNotFoundError(f"Категорію зі slug '{slug}' не знайдено")
        return category

    def create(
        self,
        name: str,
        slug: str,
        description: str | None = None,
        category_id: UUID | None = None,
    ) -> Category:
        """Створює нову категорію."""
        category = Category.create(
            name=name,
            slug=slug,
            description=description,
            category_id=category_id,
        )
        return self._repository.add(category)

    def update(
        self,
        category_id: UUID,
        name: str | None = None,
        slug: str | None = None,
        description: str | None = None,
        is_active: bool | None = None,
    ) -> Category:
        """Оновлює атрибути категорії (FR-012)."""
        category = self.get_by_id(category_id)
        if name is not None:
            clean_name = name.strip()
            if not clean_name:
                raise InvalidCategoryError("Назва категорії не може бути порожньою")
            category.name = clean_name
        if slug is not None:
            clean_slug = slug.strip().lower()
            if not clean_slug:
                raise InvalidCategoryError("Slug категорії не може бути порожнім")
            category.slug = clean_slug
        if description is not None:
            category.description = description.strip() if description.strip() else None
        if is_active is not None:
            category.is_active = is_active
        return self._repository.update(category)

    def deactivate(self, category_id: UUID) -> Category:
        """Деактивує категорію зі збереженням запису в БД (FR-012)."""
        category = self.get_by_id(category_id)
        category.is_active = False
        return self._repository.update(category)

    def is_valid_category_id(self, category_id: UUID) -> bool:
        """Перевіряє, чи існує активна категорія із зазначеним ID."""
        cat = self._repository.get(category_id)
        return cat is not None and cat.is_active
