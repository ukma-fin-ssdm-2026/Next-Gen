"""Запити й відповіді API оцінок продавців (ADR-004)."""

from datetime import datetime
from typing import Annotated
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, StringConstraints

from src.api.schemas.listings import SellerRatingSummary
from src.domain.moderation import (
    MODERATION_REASON_MAX_LENGTH,
    MODERATION_REASON_MIN_LENGTH,
)
from src.domain.seller_reviews import MAX_RATING, MIN_RATING, SellerReviewStatus

Rating = Annotated[int, Field(strict=True, ge=MIN_RATING, le=MAX_RATING)]


class SetSellerReviewRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    rating: Rating
    listing_id: UUID | None = None


class HideSellerReviewRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    reason: Annotated[
        str,
        StringConstraints(
            strip_whitespace=True,
            min_length=MODERATION_REASON_MIN_LENGTH,
            max_length=MODERATION_REASON_MAX_LENGTH,
        ),
    ]


class OwnSellerReviewResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    review_id: UUID
    seller_id: UUID
    listing_id: UUID | None
    rating: Rating
    status: SellerReviewStatus
    created_at: datetime
    updated_at: datetime


class SellerRatingResponse(SellerRatingSummary):
    distribution: dict[int, int] | None = Field(
        ..., description="Кількість за кожним балом або null, якщо оцінок замало"
    )
    my_rating: Rating | None = Field(
        None, description="Повертається, лише якщо поточний користувач є автором оцінки"
    )


class ModeratedSellerReviewResponse(OwnSellerReviewResponse):
    author_id: UUID
    hidden_by: UUID | None
    hidden_at: datetime | None
    hidden_reason: str | None


class ReviewAuthorStatsResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    total_count: int
    recent_count: int = Field(..., description="Оцінки, створені за останні 24 години")
    recent_one_star_count: int = Field(
        ..., description="Кількість однозіркових оцінок, створених за останні 24 години"
    )


class AdminSellerReviewResponse(ModeratedSellerReviewResponse):
    author_stats: ReviewAuthorStatsResponse
