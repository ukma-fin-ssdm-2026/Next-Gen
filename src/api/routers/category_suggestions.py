"""HTTP-адаптер пропозицій нових категорій і їх модерації (FR-015 / US-010)."""

from uuid import UUID

from fastapi import APIRouter, Body, Depends, HTTPException, Query, status

from src.api.deps import (
    get_category_suggestion_service,
    require_current_user,
)
from src.api.routers.moderation import require_moderator
from src.api.schemas.category_suggestions import (
    CategorySuggestionApproveRequest,
    CategorySuggestionCreateRequest,
    CategorySuggestionRejectRequest,
    CategorySuggestionResponse,
)
from src.api.schemas.listings import ApiValidationErrorResponse, ErrorResponse
from src.domain.category_suggestions import (
    CategorySuggestion,
    CategorySuggestionStatus,
)
from src.domain.exceptions import (
    CategorySuggestionConflictError,
    CategorySuggestionNotFoundError,
    CategorySuggestionQuotaError,
    DuplicateCategorySuggestionError,
    InvalidCategorySuggestionError,
    InvalidModerationReasonError,
    ListingForbiddenError,
    ListingUnauthorizedError,
    ModerationForbiddenError,
)
from src.domain.users import CurrentUser
from src.services.category_suggestions import CategorySuggestionService

router = APIRouter(
    prefix="/category-suggestions",
    tags=["Category Suggestions"],
)


def _to_response(
    suggestion: CategorySuggestion, listings_count: int = 0
) -> CategorySuggestionResponse:
    return CategorySuggestionResponse(
        suggestion_id=suggestion.suggestion_id,
        name=suggestion.name,
        proposer_id=suggestion.proposer_id,
        status=suggestion.status,
        reason=suggestion.reason,
        category_id=suggestion.category_id,
        reviewed_by=suggestion.reviewed_by,
        created_at=suggestion.created_at,
        reviewed_at=suggestion.reviewed_at,
        listings_count=listings_count,
    )


def _raise_suggestion_error(exc: Exception, field_name: str = "name") -> None:
    if isinstance(exc, (InvalidCategorySuggestionError, InvalidModerationReasonError)):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail=[
                {
                    "loc": ["body", field_name],
                    "msg": str(exc),
                    "type": "value_error",
                }
            ],
        ) from exc
    if isinstance(exc, ListingUnauthorizedError):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail=str(exc)
        ) from exc
    if isinstance(exc, (ListingForbiddenError, ModerationForbiddenError)):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail=str(exc)
        ) from exc
    if isinstance(exc, CategorySuggestionNotFoundError):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)
        ) from exc
    if isinstance(
        exc, (DuplicateCategorySuggestionError, CategorySuggestionConflictError)
    ):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail=str(exc)
        ) from exc
    if isinstance(exc, CategorySuggestionQuotaError):
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS, detail=str(exc)
        ) from exc
    raise exc


@router.post(
    "",
    response_model=CategorySuggestionResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Створити пропозицію нової категорії",
    description=(
        "Дозволяє автентифікованому користувачеві подати пропозицію нової категорії "
        "(FR-015 / US-010). Не більше 3 пропозицій у статусі PENDING на користувача."
    ),
    responses={
        401: {"model": ErrorResponse, "description": "Unauthorized"},
        403: {"model": ErrorResponse, "description": "Forbidden"},
        409: {"model": ErrorResponse, "description": "Conflict"},
        422: {"model": ApiValidationErrorResponse, "description": "Validation Error"},
        429: {"model": ErrorResponse, "description": "Too Many Requests"},
    },
)
def submit_category_suggestion(
    payload: CategorySuggestionCreateRequest,
    current_user: CurrentUser = Depends(require_current_user),
    service: CategorySuggestionService = Depends(get_category_suggestion_service),
) -> CategorySuggestionResponse:
    try:
        suggestion = service.submit(current_user, payload.name)
    except Exception as exc:
        _raise_suggestion_error(exc, field_name="name")
    return _to_response(
        suggestion, service.count_active_listings(suggestion.suggestion_id)
    )


@router.get(
    "",
    response_model=list[CategorySuggestionResponse],
    summary="Черга пропозицій категорій для модерації",
    description=(
        "Повертає список пропозицій категорій із фільтром за статусом та кількістю "
        "прив'язаних активних оголошень (FR-015). Доступно лише для ролі ADMIN."
    ),
    responses={
        401: {"model": ErrorResponse, "description": "Unauthorized"},
        403: {"model": ErrorResponse, "description": "Forbidden"},
        422: {"model": ApiValidationErrorResponse, "description": "Validation Error"},
    },
)
def list_category_suggestions(
    suggestion_status: CategorySuggestionStatus = Query(
        CategorySuggestionStatus.PENDING,
        alias="status",
        description="Фільтр за статусом пропозиції (PENDING, APPROVED, REJECTED)",
    ),
    moderator: CurrentUser = Depends(require_moderator),
    service: CategorySuggestionService = Depends(get_category_suggestion_service),
) -> list[CategorySuggestionResponse]:
    items = service.list_by_status(moderator, status=suggestion_status)
    return [_to_response(item, count) for item, count in items]


@router.post(
    "/{suggestion_id}/approve",
    response_model=CategorySuggestionResponse,
    summary="Схвалити пропозицію та створити категорію",
    description=(
        "Адміністратор схвалює пропозицію категорії (FR-015): створюється нова активна "
        "категорія, усі активні оголошення з категорії «Інше» переміщуються до неї, "
        "а дія фіксується в журналі модерації."
    ),
    responses={
        401: {"model": ErrorResponse, "description": "Unauthorized"},
        403: {"model": ErrorResponse, "description": "Forbidden"},
        404: {"model": ErrorResponse, "description": "Not Found"},
        409: {"model": ErrorResponse, "description": "Conflict"},
        422: {"model": ApiValidationErrorResponse, "description": "Validation Error"},
    },
)
def approve_category_suggestion(
    suggestion_id: UUID,
    payload: CategorySuggestionApproveRequest | None = Body(default=None),
    moderator: CurrentUser = Depends(require_moderator),
    service: CategorySuggestionService = Depends(get_category_suggestion_service),
) -> CategorySuggestionResponse:
    override_name = payload.name if payload is not None else None
    try:
        approved = service.approve(moderator, suggestion_id, name=override_name)
    except Exception as exc:
        _raise_suggestion_error(exc, field_name="name")
    return _to_response(approved, service.count_active_listings(approved.suggestion_id))


@router.post(
    "/{suggestion_id}/reject",
    response_model=CategorySuggestionResponse,
    summary="Відхилити пропозицію категорії",
    description=(
        "Адміністратор відхиляє пропозицію з обов'язковою причиною (FR-015): "
        "оголошення залишаються в «Інше», а рішення фіксується в журналі модерації."
    ),
    responses={
        401: {"model": ErrorResponse, "description": "Unauthorized"},
        403: {"model": ErrorResponse, "description": "Forbidden"},
        404: {"model": ErrorResponse, "description": "Not Found"},
        409: {"model": ErrorResponse, "description": "Conflict"},
        422: {"model": ApiValidationErrorResponse, "description": "Validation Error"},
    },
)
def reject_category_suggestion(
    suggestion_id: UUID,
    payload: CategorySuggestionRejectRequest,
    moderator: CurrentUser = Depends(require_moderator),
    service: CategorySuggestionService = Depends(get_category_suggestion_service),
) -> CategorySuggestionResponse:
    try:
        rejected = service.reject(moderator, suggestion_id, reason=payload.reason)
    except Exception as exc:
        _raise_suggestion_error(exc, field_name="reason")
    return _to_response(rejected, service.count_active_listings(rejected.suggestion_id))
