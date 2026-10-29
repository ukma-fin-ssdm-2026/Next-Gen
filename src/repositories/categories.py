"""Репозиторій категорій оголошень (FR-012)."""

from typing import Protocol
from uuid import UUID

from src.domain.categories import Category
from src.domain.exceptions import CategoryNotFoundError, DuplicateCategoryError
from src.domain.listings import OTHER_CATEGORY_ID, SEED_CATEGORY_ID

SEED_CATEGORIES = [
    Category(
        id=SEED_CATEGORY_ID,
        name="Підручники та конспекти",
        slug="textbooks",
        description="Навчальна література, посібники, конспекти лекцій НаУКМА",
        is_active=True,
    ),
    Category(
        id=UUID("22222222-2222-2222-2222-222222222222"),
        name="Електроніка та техніка",
        slug="electronics",
        description="Ноутбуки, аксесуари, зарядні пристрої, калькулятори",
        is_active=True,
    ),
    Category(
        id=UUID("33333333-3333-3333-3333-333333333333"),
        name="Одяг та мерч Могилянки",
        slug="clothing",
        description="Фірмові худі НаУКМА, футболки, сумки та аксесуари",
        is_active=True,
    ),
    Category(
        id=UUID("44444444-4444-4444-4444-444444444444"),
        name="Канцелярія та побут",
        slug="stationery",
        description="Зошити, приладдя для письма, побутові речі для гуртожитку",
        is_active=True,
    ),
    Category(
        id=OTHER_CATEGORY_ID,
        name="Інше",
        slug="other",
        description="Різні корисні дрібниці",
        is_active=True,
    ),
]


class CategoryRepository(Protocol):
    """Інтерфейс сховища категорій."""

    def get(self, category_id: UUID) -> Category | None: ...

    def get_by_slug(self, slug: str) -> Category | None: ...

    def get_by_name(self, name: str) -> Category | None: ...

    def list_all(self) -> list[Category]: ...

    def list_active(self) -> list[Category]: ...

    def add(self, category: Category) -> Category: ...

    def update(self, category: Category) -> Category: ...

    def delete(self, category_id: UUID) -> bool: ...


class InMemoryCategoryRepository:
    """In-memory реалізація сховища категорій для швидкого тестування та розробки."""

    def __init__(self, categories: list[Category] | None = None) -> None:
        self._items: dict[UUID, Category] = {}
        if categories:
            for cat in categories:
                self._items[cat.id] = cat

    @classmethod
    def with_seed(cls) -> "InMemoryCategoryRepository":
        """Фабрика зі стандартними категоріями НаУКМА."""
        return cls([Category(**cat.__dict__) for cat in SEED_CATEGORIES])

    def get(self, category_id: UUID) -> Category | None:
        return self._items.get(category_id)

    def get_by_slug(self, slug: str) -> Category | None:
        clean_slug = slug.strip().lower()
        for cat in self._items.values():
            if cat.slug == clean_slug:
                return cat
        return None

    def get_by_name(self, name: str) -> Category | None:
        key = name.strip().casefold()
        for cat in self._items.values():
            if cat.name.strip().casefold() == key:
                return cat
        return None

    def list_all(self) -> list[Category]:
        return list(self._items.values())

    def list_active(self) -> list[Category]:
        return [cat for cat in self._items.values() if cat.is_active]

    def add(self, category: Category) -> Category:
        existing = self.get_by_slug(category.slug)
        if existing is not None and existing.id != category.id:
            raise DuplicateCategoryError(
                f"Категорія зі slug '{category.slug}' вже існує"
            )
        self._items[category.id] = category
        return category

    def update(self, category: Category) -> Category:
        if category.id not in self._items:
            raise CategoryNotFoundError(f"Категорію {category.id} не знайдено")
        existing = self.get_by_slug(category.slug)
        if existing is not None and existing.id != category.id:
            raise DuplicateCategoryError(
                f"Категорія зі slug '{category.slug}' вже існує"
            )
        self._items[category.id] = category
        return category

    def delete(self, category_id: UUID) -> bool:
        return self._items.pop(category_id, None) is not None
