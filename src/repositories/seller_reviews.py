"""Контракт і локальне сховище оцінок продавців (FR-019, FR-020)."""

from collections import Counter
from collections.abc import Iterator
from contextlib import AbstractContextManager, contextmanager
from dataclasses import replace
from datetime import datetime
from threading import RLock
from typing import Protocol
from uuid import UUID

from src.domain.seller_reviews import (
    ReviewAuthorStats,
    SellerReview,
    SellerReviewStatus,
)


class SellerReviewRepository(Protocol):
    def lock_author(self, author_id: UUID) -> AbstractContextManager[None]: ...

    def lock_review(
        self, review_id: UUID
    ) -> AbstractContextManager[SellerReview | None]: ...

    def find(self, author_id: UUID, seller_id: UUID) -> SellerReview | None: ...

    def upsert(self, review: SellerReview) -> tuple[SellerReview, bool]: ...

    def delete(
        self, author_id: UUID, seller_id: UUID, at: datetime
    ) -> SellerReview | None: ...

    def save_moderation(self, review: SellerReview) -> None: ...

    def visible_distribution(self, seller_id: UUID) -> dict[int, int]: ...

    def list_reviews(
        self, seller_id: UUID | None, author_id: UUID | None, skip: int, limit: int
    ) -> list[SellerReview]: ...

    def author_stats(
        self, author_ids: set[UUID], since: datetime
    ) -> dict[UUID, ReviewAuthorStats]: ...


class InMemorySellerReviewRepository:
    def __init__(self) -> None:
        self._reviews: dict[tuple[UUID, UUID], SellerReview] = {}
        self._lock = RLock()

    @contextmanager
    def lock_author(self, author_id: UUID) -> Iterator[None]:
        with self._lock:
            yield

    @contextmanager
    def lock_review(self, review_id: UUID) -> Iterator[SellerReview | None]:
        with self._lock:
            yield next(
                (
                    item
                    for item in self._reviews.values()
                    if item.review_id == review_id
                ),
                None,
            )

    def find(self, author_id: UUID, seller_id: UUID) -> SellerReview | None:
        with self._lock:
            review = self._reviews.get((author_id, seller_id))
            return review if review is not None and review.deleted_at is None else None

    def upsert(self, review: SellerReview) -> tuple[SellerReview, bool]:
        key = (review.author_id, review.seller_id)
        with self._lock:
            previous = self._reviews.get(key)
            saved = (
                review
                if previous is None
                else replace(
                    previous,
                    rating=review.rating,
                    listing_id=review.listing_id,
                    deleted_at=None,
                    updated_at=review.updated_at,
                )
            )
            self._reviews[key] = saved
            return saved, previous is None

    def delete(
        self, author_id: UUID, seller_id: UUID, at: datetime
    ) -> SellerReview | None:
        key = (author_id, seller_id)
        with self._lock:
            review = self.find(author_id, seller_id)
            if review is None:
                return None
            if review.status == SellerReviewStatus.HIDDEN:
                self._reviews[key] = replace(review, deleted_at=at, updated_at=at)
            else:
                del self._reviews[key]
            return review

    def save_moderation(self, review: SellerReview) -> None:
        key = (review.author_id, review.seller_id)
        with self._lock:
            if (
                review.deleted_at is not None
                and review.status == SellerReviewStatus.VISIBLE
            ):
                del self._reviews[key]
            else:
                self._reviews[key] = review

    def visible_distribution(self, seller_id: UUID) -> dict[int, int]:
        with self._lock:
            return dict(
                Counter(
                    review.rating
                    for review in self._reviews.values()
                    if review.seller_id == seller_id
                    and review.status == SellerReviewStatus.VISIBLE
                )
            )

    def list_reviews(
        self, seller_id: UUID | None, author_id: UUID | None, skip: int, limit: int
    ) -> list[SellerReview]:
        with self._lock:
            items = [
                review
                for review in self._reviews.values()
                if seller_id in (None, review.seller_id)
                and author_id in (None, review.author_id)
            ]
        items.sort(key=lambda item: (item.created_at, item.review_id), reverse=True)
        return items[skip : skip + limit]

    def author_stats(
        self, author_ids: set[UUID], since: datetime
    ) -> dict[UUID, ReviewAuthorStats]:
        totals: Counter[UUID] = Counter()
        recent: Counter[UUID] = Counter()
        recent_one_star: Counter[UUID] = Counter()
        with self._lock:
            for review in self._reviews.values():
                if review.author_id in author_ids and review.deleted_at is None:
                    totals[review.author_id] += 1
                    if review.created_at > since:
                        recent[review.author_id] += 1
                        if review.rating == 1:
                            recent_one_star[review.author_id] += 1
        return {
            author_id: ReviewAuthorStats(
                count, recent[author_id], recent_one_star[author_id]
            )
            for author_id, count in totals.items()
        }
