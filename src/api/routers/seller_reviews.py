"""Публічний агрегат, власна оцінка й модерація рейтингу продавця."""

from collections.abc import Iterator
from contextlib import contextmanager
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status

from src.api.deps import (
    get_seller_review_service,
    optional_current_user,
    require_current_user,
)
from src.api.routers.moderation import require_moderator
from src.api.schemas.listings import ApiValidationErrorResponse, ErrorResponse
from src.api.schemas.seller_reviews import (
    AdminSellerReviewResponse,
    HideSellerReviewRequest,
    ModeratedSellerReviewResponse,
    OwnSellerReviewResponse,
    ReviewAuthorStatsResponse,
    SellerRatingResponse,
    SetSellerReviewRequest,
)
from src.domain.exceptions import (
    InvalidSellerReviewContextError,
    SellerReviewForbiddenError,
    SellerReviewNotFoundError,
    SellerReviewRateLimitError,
)
from src.domain.users import CurrentUser
from src.services.seller_reviews import SellerReviewService

router = APIRouter(tags=["Seller reviews"])

Reviews = Annotated[SellerReviewService, Depends(get_seller_review_service)]
Author = Annotated[CurrentUser, Depends(require_current_user)]
Moderator = Annotated[CurrentUser, Depends(require_moderator)]
Viewer = Annotated[CurrentUser | None, Depends(optional_current_user)]

UNAUTHENTICATED = {"model": ErrorResponse, "description": "Потрібна чинна сесія"}
FORBIDDEN = {"model": ErrorResponse, "description": "Дія заборонена"}
QUOTA_EXCEEDED = {"model": ErrorResponse, "description": "Вичерпано ліміт за 24 години"}
INVALID_INPUT = {"model": ApiValidationErrorResponse, "description": "Невалідні дані"}
REVIEW_NOT_FOUND = {"model": ErrorResponse, "description": "Оцінку не знайдено"}


@contextmanager
def _review_errors() -> Iterator[None]:
    try:
        yield
    except SellerReviewNotFoundError as exc:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except SellerReviewForbiddenError as exc:
        raise HTTPException(status.HTTP_403_FORBIDDEN, detail=str(exc)) from exc
    except SellerReviewRateLimitError as exc:
        raise HTTPException(status.HTTP_429_TOO_MANY_REQUESTS, detail=str(exc)) from exc
    except InvalidSellerReviewContextError as exc:
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail=[
                {"loc": ["body", "listing_id"], "msg": str(exc), "type": "value_error"}
            ],
        ) from exc


@router.put(
    "/users/{seller_id}/review",
    summary="Поставити або змінити оцінку продавця",
    responses={
        201: {"model": OwnSellerReviewResponse, "description": "Оцінку створено"},
        401: UNAUTHENTICATED,
        403: FORBIDDEN,
        404: {
            "model": ErrorResponse,
            "description": "Продавця або оголошення не знайдено",
        },
        422: INVALID_INPUT,
        429: QUOTA_EXCEEDED,
    },
)
def set_seller_review(
    seller_id: UUID,
    payload: SetSellerReviewRequest,
    response: Response,
    author: Author,
    reviews: Reviews,
) -> OwnSellerReviewResponse:
    with _review_errors():
        review, created = reviews.set_review(
            author, seller_id, payload.rating, payload.listing_id
        )
    if created:
        response.status_code = status.HTTP_201_CREATED
    return OwnSellerReviewResponse.model_validate(review)


@router.delete(
    "/users/{seller_id}/review",
    summary="Видалити свою оцінку продавця",
    status_code=status.HTTP_204_NO_CONTENT,
    responses={
        401: UNAUTHENTICATED,
        403: FORBIDDEN,
        404: REVIEW_NOT_FOUND,
        422: INVALID_INPUT,
        429: QUOTA_EXCEEDED,
    },
)
def delete_seller_review(seller_id: UUID, author: Author, reviews: Reviews) -> None:
    with _review_errors():
        reviews.remove_review(author, seller_id)


@router.get(
    "/users/{seller_id}/rating",
    response_model_exclude_unset=True,
    summary="Отримати видимий рейтинг продавця",
    responses={
        404: {"model": ErrorResponse, "description": "Продавця не знайдено"},
        422: INVALID_INPUT,
    },
)
def get_seller_rating(
    seller_id: UUID, response: Response, viewer: Viewer, reviews: Reviews
) -> SellerRatingResponse:
    with _review_errors():
        aggregate, own_rating = reviews.get_rating(seller_id, viewer)

    response.headers["Cache-Control"] = "private, no-store"
    rating = SellerRatingResponse(
        average=aggregate.average,
        count=aggregate.count,
        distribution=aggregate.distribution,
    )
    if own_rating is not None:
        rating.my_rating = own_rating
    return rating


@router.get(
    "/admin/reviews",
    summary="Переглянути оцінки та статистику їх авторів",
    responses={401: UNAUTHENTICATED, 403: FORBIDDEN, 422: INVALID_INPUT},
)
def list_seller_reviews(
    moderator: Moderator,
    reviews: Reviews,
    seller_id: UUID | None = None,
    author_id: UUID | None = None,
    skip: Annotated[int, Query(ge=0)] = 0,
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
) -> list[AdminSellerReviewResponse]:
    with _review_errors():
        items, stats = reviews.list_for_moderation(
            moderator, seller_id, author_id, skip, limit
        )
    return [
        AdminSellerReviewResponse(
            **ModeratedSellerReviewResponse.model_validate(item).model_dump(),
            author_stats=ReviewAuthorStatsResponse.model_validate(
                stats[item.author_id]
            ),
        )
        for item in items
    ]


@router.post(
    "/admin/reviews/{review_id}/hide",
    summary="Приховати оцінку з обов'язковою причиною",
    responses={
        401: UNAUTHENTICATED,
        403: FORBIDDEN,
        404: REVIEW_NOT_FOUND,
        422: INVALID_INPUT,
    },
)
def hide_seller_review(
    review_id: UUID,
    payload: HideSellerReviewRequest,
    moderator: Moderator,
    reviews: Reviews,
) -> ModeratedSellerReviewResponse:
    with _review_errors():
        review = reviews.moderate(moderator, review_id, hide_reason=payload.reason)
    return ModeratedSellerReviewResponse.model_validate(review)


@router.post(
    "/admin/reviews/{review_id}/restore",
    summary="Відновити видимість оцінки",
    responses={
        401: UNAUTHENTICATED,
        403: FORBIDDEN,
        404: REVIEW_NOT_FOUND,
        422: INVALID_INPUT,
    },
)
def restore_seller_review(
    review_id: UUID, moderator: Moderator, reviews: Reviews
) -> ModeratedSellerReviewResponse:
    with _review_errors():
        review = reviews.moderate(moderator, review_id, hide_reason=None)
    return ModeratedSellerReviewResponse.model_validate(review)
