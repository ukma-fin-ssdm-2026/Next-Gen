"""Оцінки продавців і правила їх публічного відображення (ADR-004)."""

from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import StrEnum
from uuid import UUID, uuid4

from src.domain.users import utc_now

MIN_RATING = 1
MAX_RATING = 5
REVIEW_MUTATION_LIMIT = 10
REVIEW_WINDOW = timedelta(hours=24)


class SellerReviewStatus(StrEnum):
    VISIBLE = "VISIBLE"
    HIDDEN = "HIDDEN"


@dataclass(frozen=True)
class SellerReview:
    seller_id: UUID
    author_id: UUID
    rating: int
    listing_id: UUID | None = None
    review_id: UUID = field(default_factory=uuid4)
    status: SellerReviewStatus = SellerReviewStatus.VISIBLE
    hidden_by: UUID | None = None
    hidden_at: datetime | None = None
    hidden_reason: str | None = None
    created_at: datetime = field(default_factory=utc_now)
    updated_at: datetime = field(default_factory=utc_now)

    def __post_init__(self) -> None:
        if type(self.rating) is not int or not MIN_RATING <= self.rating <= MAX_RATING:
            raise ValueError("Оцінка має бути цілим числом від 1 до 5")


@dataclass(frozen=True)
class SellerRating:
    average: float | None
    count: int
    distribution: dict[int, int] | None


@dataclass(frozen=True)
class ReviewAuthorStats:
    total_count: int
    recent_count: int
    recent_one_star_count: int
