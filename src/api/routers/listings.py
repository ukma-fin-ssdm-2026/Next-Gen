"""HTTP-адаптер до Listing Service. Бізнес-правила тут не живуть."""

from typing import Annotated, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, Header, HTTPException, Query, status

from src.api.deps import get_listing_service
from src.api.schemas.listings import (
    ErrorResponse,
    HTTPValidationError,
    ListingCreate,
    ListingImageResponse,
    ListingPublicResponse,
    ListingResponse,
    ListingUpdate,
)
from src.domain.exceptions import (
    InvalidCategoryError,
    InvalidListingImageError,
    InvalidPriceRangeError,
    ListingForbiddenError,
    ListingNotFoundError,
    ListingUnauthorizedError,
)
from src.domain.listings import Listing, ListingSortOrder
from src.services.listings import ListingService

router = APIRouter(
    prefix="/listings",
    tags=["Listings"],
)

ActorId = Annotated[
    Optional[UUID],
    Header(
        alias="X-Actor-Id",
        description=(
            "Тимчасовий ідентифікатор користувача до впровадження JWT (ADR-003). "
            "Сервер не приймає user_id з тіла запиту."
        ),
    ),
]


def _to_public(listing: Listing) -> ListingPublicResponse:
    """Публічна схема без contact (SEC-002, TM-05)."""
    return ListingPublicResponse(
        id=listing.id,
        title=listing.title,
        description=listing.description,
        price=listing.price,
        category_id=listing.category_id,
        condition=listing.condition,
        user_id=listing.user_id,
        status=listing.status.value,
        images=[
            ListingImageResponse(
                image_id=image.image_id,
                image_url=image.image_url,
                display_order=image.display_order,
            )
            for image in listing.images
        ],
        created_at=listing.created_at,
        updated_at=listing.updated_at,
    )


def _to_private(listing: Listing) -> ListingResponse:
    """Повна схема для власника після create/update та у власній історії."""
    return ListingResponse(
        **_to_public(listing).model_dump(),
        contact=listing.contact,
    )


def _raise_domain(exc: Exception) -> None:
    if isinstance(exc, InvalidPriceRangeError):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail=[
                {
                    "loc": ["query", "min_price"],
                    "msg": str(exc),
                    "type": "value_error",
                }
            ],
        )
    if isinstance(exc, InvalidListingImageError):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail=[
                {
                    "loc": ["body", "image_urls"],
                    "msg": str(exc),
                    "type": "value_error",
                }
            ],
        )
    if isinstance(exc, ListingUnauthorizedError):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=str(exc))
    if isinstance(exc, ListingForbiddenError):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(exc))
    if isinstance(exc, ListingNotFoundError):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))
    if isinstance(exc, InvalidCategoryError):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))
    raise exc


@router.get(
    "",
    response_model=list[ListingPublicResponse],
    summary="Отримати список оголошень (публічний)",
    description=(
        "Повертає активні оголошення з пагінацією, фільтром категорії, діапазоном "
        "ціни та текстовим пошуком (FR-006, FR-007, FR-008). "
        "Контакт продавця не включається."
    ),
    responses={
        422: {
            "model": HTTPValidationError,
            "description": "Validation Error",
        },
    },
)
def get_listings(
    skip: int = Query(0, ge=0, description="Кількість пропущених записів"),
    limit: int = Query(10, ge=1, le=100, description="Розмір сторінки"),
    category_id: Optional[UUID] = Query(None, description="Фільтр за категорією"),
    q: Optional[str] = Query(
        None,
        min_length=1,
        max_length=100,
        description="Пошук за назвою та описом",
    ),
    min_price: Optional[float] = Query(None, ge=0, description="Мінімальна ціна"),
    max_price: Optional[float] = Query(None, ge=0, description="Максимальна ціна"),
    sort_order: ListingSortOrder = Query(
        ListingSortOrder.NEWEST,
        alias="sort",
        description="Порядок за датою публікації: newest або oldest",
    ),
    service: ListingService = Depends(get_listing_service),
) -> list[ListingPublicResponse]:
    try:
        items = service.list_public(
            skip=skip,
            limit=limit,
            category_id=category_id,
            query=q,
            min_price=min_price,
            max_price=max_price,
            sort_order=sort_order,
        )
    except InvalidPriceRangeError as exc:
        _raise_domain(exc)
    return [_to_public(item) for item in items]


@router.get(
    "/my",
    response_model=list[ListingPublicResponse],
    summary="Отримати історію власних оголошень продавця",
    description=(
        "Повертає перелік активних і знятих з публікації оголошень поточного "
        "користувача з відповідним статусом кожного оголошення (FR-005)."
    ),
    responses={
        401: {"model": ErrorResponse, "description": "Unauthorized"},
        422: {"model": HTTPValidationError, "description": "Validation Error"},
    },
)
def get_my_listings(
    actor_id: ActorId = None,
    service: ListingService = Depends(get_listing_service),
) -> list[ListingPublicResponse]:
    try:
        items = service.list_owner_listings(actor_id=actor_id)
    except ListingUnauthorizedError as exc:
        _raise_domain(exc)
    return [_to_public(item) for item in items]


@router.post(
    "",
    response_model=ListingResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Створити оголошення",
    description=(
        "Створює оголошення від імені X-Actor-Id із підтримкою фотографій "
        "та стану товару (FR-002). Повертає об'єкт з контактами."
    ),
    responses={
        400: {"model": ErrorResponse, "description": "Bad Request"},
        401: {"model": ErrorResponse, "description": "Unauthorized"},
        422: {"model": HTTPValidationError, "description": "Validation Error"},
    },
)
def create_listing(
    listing: ListingCreate,
    actor_id: ActorId = None,
    service: ListingService = Depends(get_listing_service),
) -> ListingResponse:
    try:
        created = service.create(
            actor_id=actor_id,
            title=listing.title,
            description=listing.description,
            price=listing.price,
            category_id=listing.category_id,
            contact=listing.contact,
            condition=listing.condition,
            image_urls=listing.image_urls,
        )
    except (
        ListingUnauthorizedError,
        InvalidListingImageError,
        InvalidCategoryError,
    ) as exc:
        _raise_domain(exc)
    return _to_private(created)


@router.get(
    "/{listing_id}",
    response_model=ListingPublicResponse,
    summary="Отримати оголошення за ID (публічне)",
    description="Деталі активного оголошення без контактів.",
    responses={
        404: {"model": ErrorResponse, "description": "Not Found"},
        422: {"model": HTTPValidationError, "description": "Validation Error"},
    },
)
def get_listing(
    listing_id: UUID,
    service: ListingService = Depends(get_listing_service),
) -> ListingPublicResponse:
    try:
        listing = service.get_public(listing_id)
    except ListingNotFoundError as exc:
        _raise_domain(exc)
    return _to_public(listing)


@router.patch(
    "/{listing_id}",
    response_model=ListingPublicResponse,
    summary="Частково оновити оголошення",
    description="Оновлює лише оголошення поточного користувача (заголовок X-Actor-Id).",
    responses={
        401: {"model": ErrorResponse, "description": "Unauthorized"},
        403: {"model": ErrorResponse, "description": "Forbidden"},
        404: {"model": ErrorResponse, "description": "Not Found"},
        422: {"model": HTTPValidationError, "description": "Validation Error"},
    },
)
def update_listing(
    listing_id: UUID,
    listing_update: ListingUpdate,
    actor_id: ActorId = None,
    service: ListingService = Depends(get_listing_service),
) -> ListingPublicResponse:
    try:
        updated = service.update(
            listing_id=listing_id,
            actor_id=actor_id,
            **listing_update.model_dump(exclude_unset=True),
        )
    except (
        ListingUnauthorizedError,
        ListingForbiddenError,
        ListingNotFoundError,
        InvalidListingImageError,
    ) as exc:
        _raise_domain(exc)
    return _to_public(updated)


@router.delete(
    "/{listing_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Видалити оголошення",
    description=(
        "Знімає оголошення з публікації (переводить у WITHDRAWN, FR-004). "
        "Виконується лише власником."
    ),
    responses={
        401: {"model": ErrorResponse, "description": "Unauthorized"},
        403: {"model": ErrorResponse, "description": "Forbidden"},
        404: {"model": ErrorResponse, "description": "Not Found"},
        422: {"model": HTTPValidationError, "description": "Validation Error"},
    },
)
def delete_listing(
    listing_id: UUID,
    actor_id: ActorId = None,
    service: ListingService = Depends(get_listing_service),
) -> None:
    try:
        service.delete(listing_id, actor_id)
    except (
        ListingUnauthorizedError,
        ListingForbiddenError,
        ListingNotFoundError,
    ) as exc:
        _raise_domain(exc)
