"""HTTP-адаптер до Favorite Service (FR-009). Бізнес-правила тут не живуть."""

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status

from src.api.deps import get_favorite_service
from src.api.routers.listings import ActorId, _to_public
from src.api.schemas.favorites import FavoriteResponse
from src.api.schemas.listings import (
    ApiValidationErrorResponse,
    ErrorResponse,
    ListingPublicResponse,
)
from src.domain.exceptions import (
    FavoriteNotFoundError,
    ListingNotFoundError,
    ListingUnauthorizedError,
)
from src.services.favorites import FavoriteService

router = APIRouter(
    prefix="/favorites",
    tags=["Favorites"],
)


def _raise_domain(exc: Exception) -> None:
    if isinstance(exc, ListingUnauthorizedError):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=str(exc))
    if isinstance(exc, (ListingNotFoundError, FavoriteNotFoundError)):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))
    raise exc


@router.get(
    "",
    response_model=list[ListingPublicResponse],
    summary="Отримати власне обране",
    description=(
        "Повертає активні оголошення з обраного поточного користувача, "
        "спершу додані останніми (FR-009). Контакти продавців не включаються."
    ),
    responses={
        401: {"model": ErrorResponse, "description": "Unauthorized"},
        422: {"model": ApiValidationErrorResponse, "description": "Validation Error"},
    },
)
def get_favorites(
    actor_id: ActorId = None,
    service: FavoriteService = Depends(get_favorite_service),
) -> list[ListingPublicResponse]:
    try:
        items = service.list_for(actor_id)
    except ListingUnauthorizedError as exc:
        _raise_domain(exc)
    return [_to_public(item) for item in items]


@router.post(
    "/{listing_id}",
    response_model=FavoriteResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Додати оголошення в обране",
    description=(
        "Додає активне оголошення в обране поточного користувача (FR-009). "
        "Повторне додавання не створює дубліката і повертає наявний запис."
    ),
    responses={
        401: {"model": ErrorResponse, "description": "Unauthorized"},
        404: {"model": ErrorResponse, "description": "Not Found"},
        422: {"model": ApiValidationErrorResponse, "description": "Validation Error"},
    },
)
def add_favorite(
    listing_id: UUID,
    actor_id: ActorId = None,
    service: FavoriteService = Depends(get_favorite_service),
) -> FavoriteResponse:
    try:
        favorite = service.add(actor_id, listing_id)
    except (ListingUnauthorizedError, ListingNotFoundError) as exc:
        _raise_domain(exc)
    return FavoriteResponse(
        listing_id=favorite.listing_id, created_at=favorite.created_at
    )


@router.delete(
    "/{listing_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Прибрати оголошення з обраного",
    description="Видаляє оголошення з обраного поточного користувача (FR-009).",
    responses={
        401: {"model": ErrorResponse, "description": "Unauthorized"},
        404: {"model": ErrorResponse, "description": "Not Found"},
        422: {"model": ApiValidationErrorResponse, "description": "Validation Error"},
    },
)
def remove_favorite(
    listing_id: UUID,
    actor_id: ActorId = None,
    service: FavoriteService = Depends(get_favorite_service),
) -> None:
    try:
        service.remove(actor_id, listing_id)
    except (ListingUnauthorizedError, FavoriteNotFoundError) as exc:
        _raise_domain(exc)
