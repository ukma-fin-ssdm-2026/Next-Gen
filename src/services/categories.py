"""Category Service: бізнес-логіка керування категоріями (FR-012, REL-001)."""

from uuid import UUID

from src.domain.categories import Category
from src.domain.exceptions import CategoryNotFoundError
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

    def deactivate(self, category_id: UUID) -> Category:
        """Деактивує категорію зі збереженням запису в БД (REL-001)."""
        category = self.get_by_id(category_id)
        category.is_active = False
        return self._repository.update(category)

    def is_valid_category_id(self, category_id: UUID) -> bool:
        """Перевіряє, чи існує активна категорія із зазначеним ID."""
        cat = self._repository.get(category_id)
        return cat is not None and cat.is_active
