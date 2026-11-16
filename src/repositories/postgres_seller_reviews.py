"""PostgreSQL-адаптер оцінок продавців (ADR-004)."""

from collections.abc import Iterator
from contextlib import contextmanager
from datetime import datetime
from uuid import UUID

from sqlalchemy import delete, func, select, update
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from src.db.converters import (
    seller_review_domain_to_values,
    seller_review_row_to_domain,
)
from src.db.models import SellerReviewRow, UserRow
from src.domain.seller_reviews import (
    ReviewAuthorStats,
    SellerReview,
    SellerReviewStatus,
)


class PostgresSellerReviewRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    @contextmanager
    def lock_author(self, author_id: UUID) -> Iterator[None]:
        # FOR NO KEY UPDATE serializes each author's quota checks until commit.
        # It allows FK key-share locks when two users rate each other.
        self._session.execute(
            select(UserRow.user_id)
            .where(UserRow.user_id == author_id)
            .with_for_update(key_share=True)
        ).scalar_one_or_none()
        yield

    @contextmanager
    def lock_review(self, review_id: UUID) -> Iterator[SellerReview | None]:
        row = self._session.execute(
            select(SellerReviewRow)
            .where(SellerReviewRow.review_id == review_id)
            .with_for_update()
        ).scalar_one_or_none()
        yield seller_review_row_to_domain(row) if row is not None else None

    def find(self, author_id: UUID, seller_id: UUID) -> SellerReview | None:
        row = self._session.execute(
            select(SellerReviewRow).where(
                SellerReviewRow.author_id == author_id,
                SellerReviewRow.seller_id == seller_id,
            )
        ).scalar_one_or_none()
        return seller_review_row_to_domain(row) if row is not None else None

    def upsert(self, review: SellerReview) -> tuple[SellerReview, bool]:
        stmt = insert(SellerReviewRow).values(seller_review_domain_to_values(review))
        stmt = stmt.on_conflict_do_update(
            constraint="uq_seller_reviews_author_seller",
            set_={
                "rating": stmt.excluded.rating,
                "listing_id": stmt.excluded.listing_id,
                "updated_at": stmt.excluded.updated_at,
            },
        ).returning(SellerReviewRow)
        row = self._session.execute(
            stmt, execution_options={"populate_existing": True}
        ).scalar_one()
        return seller_review_row_to_domain(row), row.review_id == review.review_id

    def delete(self, author_id: UUID, seller_id: UUID) -> SellerReview | None:
        row = self._session.execute(
            delete(SellerReviewRow)
            .where(
                SellerReviewRow.author_id == author_id,
                SellerReviewRow.seller_id == seller_id,
            )
            .returning(SellerReviewRow)
        ).scalar_one_or_none()
        return seller_review_row_to_domain(row) if row is not None else None

    def save_moderation(self, review: SellerReview) -> None:
        self._session.execute(
            update(SellerReviewRow)
            .where(SellerReviewRow.review_id == review.review_id)
            .values(
                status=review.status.value,
                hidden_by=review.hidden_by,
                hidden_at=review.hidden_at,
                hidden_reason=review.hidden_reason,
                updated_at=review.updated_at,
            )
        )

    def visible_distribution(self, seller_id: UUID) -> dict[int, int]:
        rows = self._session.execute(
            select(SellerReviewRow.rating, func.count())
            .where(
                SellerReviewRow.seller_id == seller_id,
                SellerReviewRow.status == SellerReviewStatus.VISIBLE.value,
            )
            .group_by(SellerReviewRow.rating)
        )
        return {rating: count for rating, count in rows}

    def list_reviews(
        self, seller_id: UUID | None, author_id: UUID | None, skip: int, limit: int
    ) -> list[SellerReview]:
        stmt = select(SellerReviewRow)
        if seller_id is not None:
            stmt = stmt.where(SellerReviewRow.seller_id == seller_id)
        if author_id is not None:
            stmt = stmt.where(SellerReviewRow.author_id == author_id)
        stmt = (
            stmt.order_by(
                SellerReviewRow.created_at.desc(), SellerReviewRow.review_id.desc()
            )
            .offset(skip)
            .limit(limit)
        )
        return [seller_review_row_to_domain(row) for row in self._session.scalars(stmt)]

    def author_stats(
        self, author_ids: set[UUID], since: datetime
    ) -> dict[UUID, ReviewAuthorStats]:
        if not author_ids:
            return {}
        rows = self._session.execute(
            select(
                SellerReviewRow.author_id,
                func.count(),
                func.count().filter(SellerReviewRow.created_at > since),
                func.count().filter(
                    SellerReviewRow.created_at > since, SellerReviewRow.rating == 1
                ),
            )
            .where(SellerReviewRow.author_id.in_(author_ids))
            .group_by(SellerReviewRow.author_id)
        )
        return {
            author_id: ReviewAuthorStats(total, recent, recent_one_star)
            for author_id, total, recent, recent_one_star in rows
        }
