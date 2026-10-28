"""Модульні тести для категорій оголошень (FR-012).

Тести як специфікація: визначають поведінку сутності Category,
репозиторію InMemoryCategoryRepository та сервісу CategoryService.
Тест-кейси: TP-015 (модульний рівень).
"""

from uuid import uuid4
import pytest

from src.domain.categories import Category
from src.domain.exceptions import (
    CategoryNotFoundError,
    DuplicateCategoryError,
    InvalidCategoryError,
)
from src.domain.listings import SEED_CATEGORY_ID
from src.repositories.categories import InMemoryCategoryRepository
from src.services.categories import CategoryService


@pytest.fixture
def category_repo() -> InMemoryCategoryRepository:
    return InMemoryCategoryRepository.with_seed()


@pytest.fixture
def category_service(category_repo: InMemoryCategoryRepository) -> CategoryService:
    return CategoryService(category_repo)


def test_category_creation_and_attributes() -> None:
    """[TP-015] [FR-012] Перевірка створення сутності Category та її атрибутів."""
    cat_id = uuid4()
    cat = Category(
        id=cat_id,
        name="Підручники ФІ",
        slug="fi-textbooks",
        description="Підручники факультету інформатики",
        is_active=True,
    )
    assert cat.id == cat_id
    assert cat.name == "Підручники ФІ"
    assert cat.slug == "fi-textbooks"
    assert cat.description == "Підручники факультету інформатики"
    assert cat.is_active is True


def test_category_slug_normalization_and_validation() -> None:
    """[TP-015] [FR-012] Нормалізація та валідація назви і slug категорії."""
    cat = Category.create(
        name="  Мерч НаУКМА  ",
        slug="  Merch-NaUKMA  ",
        description="Офіційний мерч",
    )
    assert cat.name == "Мерч НаУКМА"
    assert cat.slug == "merch-naukma"
    assert cat.is_active is True

    with pytest.raises(
        InvalidCategoryError, match="Назва категорії не може бути порожньою"
    ):
        Category.create(name="   ", slug="valid-slug")

    with pytest.raises(
        InvalidCategoryError, match="Slug категорії не може бути порожнім"
    ):
        Category.create(name="Valid Name", slug="   ")


def test_category_repository_seed_contains_seed_category_id(
    category_repo: InMemoryCategoryRepository,
) -> None:
    """[TP-015] [FR-012] Перевірка наявності канонічної категорії SEED_CATEGORY_ID."""
    category = category_repo.get(SEED_CATEGORY_ID)
    assert category is not None
    assert category.id == SEED_CATEGORY_ID
    assert category.is_active is True
    assert "підручник" in category.name.lower() or "textbooks" in category.slug


def test_category_repository_get_by_slug(
    category_repo: InMemoryCategoryRepository,
) -> None:
    """[TP-015] [FR-012] Отримання категорії за slug з репозиторію."""
    category = category_repo.get_by_slug("electronics")
    assert category is not None
    assert category.slug == "electronics"
    assert category_repo.get_by_slug("non-existent-slug") is None


def test_category_repository_duplicate_slug_raises_error(
    category_repo: InMemoryCategoryRepository,
) -> None:
    """[TP-015] [FR-012] Заборона створення категорій із повторюваним slug."""
    with pytest.raises(DuplicateCategoryError, match="вже існує"):
        category_repo.add(
            Category.create(
                name="Інша електроніка",
                slug="electronics",
            )
        )


def test_category_service_list_active_categories_sorted(
    category_service: CategoryService,
) -> None:
    """[TP-015] [FR-012]
    Отримання списку активних категорій, відсортованих за назвою.
    """
    active = category_service.list_active()
    assert len(active) >= 4
    # Усі мають бути активними
    assert all(cat.is_active for cat in active)
    # Відсортовано за назвою
    names = [cat.name for cat in active]
    assert names == sorted(names)


def test_category_service_deactivate_preserves_record(
    category_service: CategoryService, category_repo: InMemoryCategoryRepository
) -> None:
    """[TP-015] [FR-012]
    Деактивація категорії зберігає запис у базі без фізичного видалення.
    """
    deactivated = category_service.deactivate(SEED_CATEGORY_ID)
    assert deactivated.id == SEED_CATEGORY_ID
    assert deactivated.is_active is False

    # Запис залишається в репозиторії для збереження зв'язків
    assert category_repo.get(SEED_CATEGORY_ID) is not None

    # Але більше не повертається у списку активних
    active_ids = [cat.id for cat in category_service.list_active()]
    assert SEED_CATEGORY_ID not in active_ids


def test_category_service_update_attributes(
    category_service: CategoryService,
) -> None:
    """[TP-015] [FR-012] Оновлення назви, опису або активності категорії."""
    updated = category_service.update(
        category_id=SEED_CATEGORY_ID,
        name="Оновлені підручники",
        description="Новий опис підручників НаУКМА",
    )
    assert updated.name == "Оновлені підручники"
    assert updated.description == "Новий опис підручників НаУКМА"


def test_category_service_get_by_id_or_raise_not_found(
    category_service: CategoryService,
) -> None:
    """[TP-015] [FR-012] Отримання за ID або виняток CategoryNotFoundError."""
    existing = category_service.get_by_id(SEED_CATEGORY_ID)
    assert existing.id == SEED_CATEGORY_ID

    non_existent = uuid4()
    with pytest.raises(CategoryNotFoundError, match="не знайдено"):
        category_service.get_by_id(non_existent)


def test_category_service_validate_category_exists(
    category_service: CategoryService,
) -> None:
    """[TP-015] [FR-012] Валідація існування активної категорії за ID."""
    assert category_service.is_valid_category_id(SEED_CATEGORY_ID) is True
    assert category_service.is_valid_category_id(uuid4()) is False
