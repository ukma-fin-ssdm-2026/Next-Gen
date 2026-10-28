"""Endpoints для категорій оголошень (FR-012)."""

from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException, status

from src.api.deps import get_category_service
from src.api.schemas.categories import CategoryResponse
from src.domain.exceptions import CategoryNotFoundError
from src.services.categories import CategoryService

router = APIRouter(prefix="/categories", tags=["Categories"])


@router.get("", response_model=list[CategoryResponse])
def list_categories(
    service: CategoryService = Depends(get_category_service),
) -> list[CategoryResponse]:
    """Повертає список доступних активних категорій для перегляду та фільтрації."""
    categories = service.list_active()
    return [CategoryResponse.model_validate(cat) for cat in categories]


@router.get(
    "/{category_id}",
    response_model=CategoryResponse,
    responses={
        status.HTTP_404_NOT_FOUND: {"description": "Категорію не знайдено"},
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
