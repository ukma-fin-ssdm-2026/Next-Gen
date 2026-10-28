"""Endpoints для категорій оголошень (FR-012)."""

from typing import Annotated, Optional
from uuid import UUID
from fastapi import APIRouter, Depends, Header, HTTPException, status

from src.api.deps import get_category_service
from src.api.schemas.categories import (
    CategoryCreateRequest,
    CategoryResponse,
    CategoryUpdateRequest,
)
from src.domain.exceptions import (
    CategoryNotFoundError,
    DuplicateCategoryError,
    InvalidCategoryError,
)
from src.services.categories import CategoryService

router = APIRouter(prefix="/categories", tags=["Categories"])

ActorRole = Annotated[
    Optional[str],
    Header(
        alias="X-Actor-Role",
        description=(
            "Тимчасовий заголовок ролі користувача (ADMIN / STUDENT) "
            "до впровадження OIDC claims (ADR-003, FR-012)."
        ),
    ),
]


def _require_admin(role: Optional[str]) -> None:
    """Перевіряє наявність адміністративних прав для операцій керування категоріями."""
    if role != "ADMIN":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Дія дозволена лише адміністраторам системи",
        )


@router.get(
    "",
    response_model=list[CategoryResponse],
    summary="Отримати список активних категорій",
    description=(
        "Публічний ендпоінт для отримання списку доступних активних категорій "
        "для фільтрації каталогу та створення нових оголошень (FR-012)."
    ),
    status_code=status.HTTP_200_OK,
)
def list_categories(
    service: CategoryService = Depends(get_category_service),
) -> list[CategoryResponse]:
    """Повертає список доступних активних категорій."""
    categories = service.list_active()
    return [CategoryResponse.model_validate(cat) for cat in categories]


@router.get(
    "/{category_id}",
    response_model=CategoryResponse,
    summary="Отримати інформацію про категорію за ID",
    description=(
        "Повертає метадані конкретної категорії оголошень за "
        "її ідентифікатором (FR-012)."
    ),
    status_code=status.HTTP_200_OK,
    responses={
        status.HTTP_404_NOT_FOUND: {"description": "Категорію не знайдено"},
        status.HTTP_422_UNPROCESSABLE_CONTENT: {
            "description": "Некоректний формат UUID"
        },
    },
)
def get_category(
    category_id: UUID,
    service: CategoryService = Depends(get_category_service),
) -> CategoryResponse:
    """Повертає інформацію про конкретну категорію за її ID."""
    try:
        category = service.get_by_id(category_id)
        return CategoryResponse.model_validate(category)
    except CategoryNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc


@router.post(
    "",
    response_model=CategoryResponse,
    summary="Створити нову категорію (Адміністратор)",
    description=(
        "Адміністративний ендпоінт для додавання нової категорії оголошень (FR-012). "
        "Вимагає ролі ADMIN (заголовок X-Actor-Role: ADMIN)."
    ),
    status_code=status.HTTP_201_CREATED,
    responses={
        status.HTTP_403_FORBIDDEN: {
            "description": "Недостатньо прав доступу (потрібна роль ADMIN)"
        },
        status.HTTP_409_CONFLICT: {"description": "Категорія з таким slug вже існує"},
        status.HTTP_422_UNPROCESSABLE_CONTENT: {
            "description": "Невалідні поля категорії"
        },
    },
)
def create_category(
    payload: CategoryCreateRequest,
    role: ActorRole = None,
    service: CategoryService = Depends(get_category_service),
) -> CategoryResponse:
    """Створює нову категорію з валідацією прав адміністратора."""
    _require_admin(role)
    try:
        category = service.create(
            name=payload.name,
            slug=payload.slug,
            description=payload.description,
        )
        return CategoryResponse.model_validate(category)
    except DuplicateCategoryError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(exc),
        ) from exc
    except InvalidCategoryError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail=str(exc),
        ) from exc


@router.patch(
    "/{category_id}",
    response_model=CategoryResponse,
    summary="Оновити або деактивувати категорію (Адміністратор)",
    description=(
        "Адміністративний ендпоінт для зміни назви, опису або "
        "деактивації категорії (FR-012). "
        "Деактивована категорія зберігається в системі для "
        "збереження цілісності наявних оголошень. "
        "Вимагає ролі ADMIN (заголовок X-Actor-Role: ADMIN)."
    ),
    status_code=status.HTTP_200_OK,
    responses={
        status.HTTP_403_FORBIDDEN: {
            "description": "Недостатньо прав доступу (потрібна роль ADMIN)"
        },
        status.HTTP_404_NOT_FOUND: {"description": "Категорію не знайдено"},
        status.HTTP_409_CONFLICT: {"description": "Новий slug вже використовується"},
        status.HTTP_422_UNPROCESSABLE_CONTENT: {
            "description": "Невалідні дані оновлення"
        },
    },
)
def update_category(
    category_id: UUID,
    payload: CategoryUpdateRequest,
    role: ActorRole = None,
    service: CategoryService = Depends(get_category_service),
) -> CategoryResponse:
    """Оновлює параметри або деактивує категорію з перевіркою прав адміністратора."""
    _require_admin(role)
    try:
        category = service.update(
            category_id=category_id,
            name=payload.name,
            slug=payload.slug,
            description=payload.description,
            is_active=payload.is_active,
        )
        return CategoryResponse.model_validate(category)
    except CategoryNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc
    except DuplicateCategoryError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(exc),
        ) from exc
    except InvalidCategoryError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail=str(exc),
        ) from exc
