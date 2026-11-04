"""HTTP-адаптер до Listing Service та фото (FR-002, FR-015, TM-02, TM-03)."""

from collections.abc import Iterator, Sequence
from typing import Optional
from uuid import UUID

from fastapi import (
    APIRouter,
    Depends,
    File,
    HTTPException,
    Query,
    Response,
    UploadFile,
    status,
)

from src.api.deps import (
    get_activity_service,
    get_image_storage,
    get_listing_service,
    require_current_user,
)
from src.api.schemas.listings import (
    ApiValidationErrorResponse,
    ErrorResponse,
    ListingCreate,
    ListingImageResponse,
    ListingPublicResponse,
    ListingResponse,
    ListingUpdate,
    UploadedImageResponse,
)
from src.domain.activity import ActivityType
from src.services.activity import ActivityLogService
from src.domain.exceptions import (
    CategorySuggestionQuotaError,
    DuplicateCategorySuggestionError,
    ImageUploadRateLimitError,
    InvalidCategoryError,
    InvalidCategorySuggestionError,
    InvalidListingImageError,
    InvalidPriceRangeError,
    ListingForbiddenError,
    ListingNotFoundError,
    ListingUnauthorizedError,
)
from src.domain.listings import MAX_LISTING_PRICE, Listing, ListingSortOrder
from src.domain.users import CurrentUser
from src.repositories.image_storage import (
    MAX_IMAGE_FILE_SIZE_BYTES,
    MAX_IMAGES_PER_LISTING,
    MIN_IMAGES_PER_LISTING,
    ImageStorage,
)
from src.services.listings import ListingService

router = APIRouter(
    prefix="/listings",
    tags=["Listings"],
)


def _to_public(listing: Listing) -> ListingPublicResponse:
    """Публічна схема без contact і без suggested_category_name (SEC-002, TM-05)."""
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
                thumbnail_url=image.thumbnail_url,
                display_order=image.display_order,
                width=image.width,
                height=image.height,
                thumbnail_width=image.thumbnail_width,
                thumbnail_height=image.thumbnail_height,
            )
            for image in listing.images
        ],
        created_at=listing.created_at,
        updated_at=listing.updated_at,
    )


def _to_private(
    listing: Listing, suggested_category_name: Optional[str] = None
) -> ListingResponse:
    """Повна схема для власника після create/update та у власній історії."""
    return ListingResponse(
        **_to_public(listing).model_dump(),
        contact=listing.contact,
        suggested_category_name=suggested_category_name,
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
    if isinstance(exc, InvalidCategorySuggestionError):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail=[
                {
                    "loc": ["body", "suggested_category_name"],
                    "msg": str(exc),
                    "type": "value_error",
                }
            ],
        )
    if isinstance(exc, DuplicateCategorySuggestionError):
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc))
    if isinstance(exc, CategorySuggestionQuotaError):
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS, detail=str(exc)
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


def _iter_upload_bytes(files: Sequence[UploadFile]) -> Iterator[bytes]:
    """Читає завантажені файли по одному, не тримаючи одночасно весь пакет у пам'яті."""
    for uploaded in files:
        chunks: list[bytes] = []
        total = 0
        try:
            uploaded.file.seek(0)
            while chunk := uploaded.file.read(1024 * 1024):
                total += len(chunk)
                if total > MAX_IMAGE_FILE_SIZE_BYTES:
                    raise HTTPException(
                        status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                        detail=[
                            {
                                "loc": ["body", "files", uploaded.filename or "file"],
                                "msg": (
                                    "Розмір файла перевищує максимально допустимі 10 МБ"
                                ),
                                "type": "value_error",
                            }
                        ],
                    )
                chunks.append(chunk)
        finally:
            uploaded.file.close()
        yield b"".join(chunks)


@router.post(
    "/images",
    response_model=list[UploadedImageResponse],
    status_code=status.HTTP_201_CREATED,
    summary="Завантажити фотографії оголошення",
    description=(
        "Приймає від 1 до 10 файлів через multipart/form-data, перевіряє фактичне "
        "декодування (JPEG, PNG, WebP, HEIC/HEIF), видаляє метадані (EXIF/GPS/XMP), "
        "оптимізує розмір (до 1600 px) та створює thumbnail (до 400 px) "
        "у WebP quality=80 (FR-002, TM-03, TM-08)."
    ),
    responses={
        401: {"model": ErrorResponse, "description": "Unauthorized"},
        403: {"model": ErrorResponse, "description": "Forbidden"},
        422: {
            "model": ApiValidationErrorResponse,
            "description": "Validation Error",
        },
        429: {"model": ErrorResponse, "description": "Too Many Requests"},
    },
)
def upload_listing_images(
    files: list[UploadFile] = File(
        ...,
        description="Список файлів фотографій (1..10 файлів до 10 МБ)",
    ),
    current_user: CurrentUser = Depends(require_current_user),
    storage: ImageStorage = Depends(get_image_storage),
) -> list[UploadedImageResponse]:
    if len(files) < MIN_IMAGES_PER_LISTING or len(files) > MAX_IMAGES_PER_LISTING:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail=[
                {
                    "loc": ["body", "files"],
                    "msg": (
                        f"Кількість файлів має бути від {MIN_IMAGES_PER_LISTING} "
                        f"до {MAX_IMAGES_PER_LISTING}"
                    ),
                    "type": "value_error",
                }
            ],
        )

    try:
        saved_images = storage.upload_images(
            _iter_upload_bytes(files),
            actor_id=current_user.user_id,
        )
    except ImageUploadRateLimitError as exc:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=str(exc),
        ) from exc
    except InvalidListingImageError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail=[
                {
                    "loc": ["body", "files"],
                    "msg": str(exc),
                    "type": "value_error",
                }
            ],
        ) from exc
    finally:
        for uploaded in files:
            uploaded.file.close()

    return [
        UploadedImageResponse(
            image_id=img.image_id,
            storage_key=img.storage_key or f"{img.image_id.hex}.webp",
            image_url=img.image_url,
            thumbnail_url=img.thumbnail_url or f"{img.image_url[:-5]}_thumb.webp",
            display_order=img.display_order,
            width=img.width,
            height=img.height,
            thumbnail_width=img.thumbnail_width,
            thumbnail_height=img.thumbnail_height,
        )
        for img in saved_images
    ]


@router.get(
    "",
    response_model=list[ListingPublicResponse],
    summary="Отримати список оголошень (публічний)",
    description=(
        "Повертає активні оголошення з пагінацією, фільтром категорії, діапазоном "
        "ціни та текстовим пошуком (FR-006, FR-007, FR-008). "
        "Контакт продавця не включається. Загальна кількість знайдених "
        "оголошень повертається в заголовку X-Total-Count."
    ),
    responses={
        422: {
            "model": ApiValidationErrorResponse,
            "description": "Validation Error",
        },
    },
)
def get_listings(
    response: Response,
    skip: int = Query(0, ge=0, description="Кількість пропущених записів"),
    limit: int = Query(10, ge=1, le=100, description="Розмір сторінки"),
    category_id: Optional[UUID] = Query(None, description="Фільтр за категорією"),
    q: Optional[str] = Query(
        None,
        min_length=1,
        max_length=100,
        description="Пошук за назвою та описом",
    ),
    min_price: Optional[float] = Query(
        None, ge=0, le=MAX_LISTING_PRICE, description="Мінімальна ціна"
    ),
    max_price: Optional[float] = Query(
        None, ge=0, le=MAX_LISTING_PRICE, description="Максимальна ціна"
    ),
    sort_order: ListingSortOrder = Query(
        ListingSortOrder.NEWEST,
        alias="sort",
        description=(
            "Порядок: newest, oldest (за датою публікації), "
            "price_asc або price_desc (за ціною)"
        ),
    ),
    service: ListingService = Depends(get_listing_service),
) -> list[ListingPublicResponse]:
    try:
        items, total = service.search_public(
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
    response.headers["X-Total-Count"] = str(total)
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
        403: {"model": ErrorResponse, "description": "Forbidden"},
        422: {
            "model": ApiValidationErrorResponse,
            "description": "Validation Error",
        },
    },
)
def get_my_listings(
    current_user: CurrentUser = Depends(require_current_user),
    service: ListingService = Depends(get_listing_service),
) -> list[ListingPublicResponse]:
    try:
        items = service.list_owner_listings(actor_id=current_user.user_id)
    except ListingUnauthorizedError as exc:
        _raise_domain(exc)
    return [_to_public(item) for item in items]


@router.post(
    "",
    response_model=ListingResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Створити оголошення",
    description=(
        "Створює оголошення від імені автентифікованого користувача із "
        "підтримкою фотографій, стану товару та необов'язкової пропозиції нової "
        "категорії (FR-002, FR-015). Повертає об'єкт з контактами."
    ),
    responses={
        400: {"model": ErrorResponse, "description": "Bad Request"},
        401: {"model": ErrorResponse, "description": "Unauthorized"},
        403: {"model": ErrorResponse, "description": "Forbidden"},
        409: {"model": ErrorResponse, "description": "Conflict"},
        422: {
            "model": ApiValidationErrorResponse,
            "description": "Validation Error",
        },
        429: {"model": ErrorResponse, "description": "Too Many Requests"},
    },
)
def create_listing(
    listing: ListingCreate,
    current_user: CurrentUser = Depends(require_current_user),
    service: ListingService = Depends(get_listing_service),
    activity: ActivityLogService = Depends(get_activity_service),
) -> ListingResponse:
    try:
        created = service.create(
            actor_id=current_user,
            title=listing.title,
            description=listing.description,
            price=listing.price,
            category_id=listing.category_id,
            contact=listing.contact,
            condition=listing.condition,
            image_urls=listing.image_urls,
            suggested_category_name=listing.suggested_category_name,
        )
    except (
        ListingUnauthorizedError,
        ListingForbiddenError,
        InvalidListingImageError,
        InvalidCategoryError,
        InvalidCategorySuggestionError,
        DuplicateCategorySuggestionError,
        CategorySuggestionQuotaError,
    ) as exc:
        _raise_domain(exc)
    activity.record(
        current_user, ActivityType.LISTING_CREATED, created.id, created.title
    )
    return _to_private(created, service.get_suggested_category_name(created))


@router.get(
    "/{listing_id}",
    response_model=ListingPublicResponse,
    summary="Отримати оголошення за ID (публічне)",
    description="Деталі активного оголошення без контактів.",
    responses={
        404: {"model": ErrorResponse, "description": "Not Found"},
        422: {
            "model": ApiValidationErrorResponse,
            "description": "Validation Error",
        },
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
    description="Оновлює лише оголошення поточного користувача (FR-003).",
    responses={
        401: {"model": ErrorResponse, "description": "Unauthorized"},
        403: {"model": ErrorResponse, "description": "Forbidden"},
        404: {"model": ErrorResponse, "description": "Not Found"},
        422: {
            "model": ApiValidationErrorResponse,
            "description": "Validation Error",
        },
    },
)
def update_listing(
    listing_id: UUID,
    listing_update: ListingUpdate,
    current_user: CurrentUser = Depends(require_current_user),
    service: ListingService = Depends(get_listing_service),
    activity: ActivityLogService = Depends(get_activity_service),
) -> ListingPublicResponse:
    try:
        updated = service.update(
            listing_id=listing_id,
            actor_id=current_user.user_id,
            **listing_update.model_dump(exclude_unset=True),
        )
    except (
        ListingUnauthorizedError,
        ListingForbiddenError,
        ListingNotFoundError,
        InvalidListingImageError,
    ) as exc:
        _raise_domain(exc)
    activity.record(
        current_user, ActivityType.LISTING_UPDATED, listing_id, updated.title
    )
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
        422: {
            "model": ApiValidationErrorResponse,
            "description": "Validation Error",
        },
    },
)
def delete_listing(
    listing_id: UUID,
    current_user: CurrentUser = Depends(require_current_user),
    service: ListingService = Depends(get_listing_service),
    activity: ActivityLogService = Depends(get_activity_service),
) -> None:
    try:
        service.delete(listing_id, current_user.user_id)
    except (
        ListingUnauthorizedError,
        ListingForbiddenError,
        ListingNotFoundError,
    ) as exc:
        _raise_domain(exc)
    activity.record(current_user, ActivityType.LISTING_WITHDRAWN, listing_id)
