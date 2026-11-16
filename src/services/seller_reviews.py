"""Бізнес-правила рейтингів і модерації оцінок продавців (ADR-004)."""

from dataclasses import replace
from datetime import datetime
from uuid import UUID

from src.domain.activity import ActivityEvent, ActivityType
from src.domain.exceptions import (
    InvalidSellerReviewContextError,
    SellerReviewForbiddenError,
    SellerReviewNotFoundError,
    SellerReviewRateLimitError,
)
from src.domain.moderation import normalize_moderation_reason
from src.domain.seller_reviews import (
    MAX_RATING,
    MIN_RATING,
    REVIEW_MUTATION_LIMIT,
    REVIEW_WINDOW,
    ReviewAuthorStats,
    SellerRating,
    SellerReview,
    SellerReviewStatus,
)
from src.domain.users import CurrentUser, UserRole, utc_now
from src.repositories.listings import ListingRepository
from src.repositories.seller_reviews import SellerReviewRepository
from src.repositories.support import ActivityRepository
from src.repositories.users import UserRepository


class SellerReviewService:
    def __init__(
        self,
        reviews: SellerReviewRepository,
        users: UserRepository,
        listings: ListingRepository,
        events: ActivityRepository,
        min_count: int,
    ) -> None:
        self._reviews = reviews
        self._users = users
        self._listings = listings
        self._events = events
        self._min_count = min_count

    def set_review(
        self, actor: CurrentUser, seller_id: UUID, rating: int, listing_id: UUID | None
    ) -> tuple[SellerReview, bool]:
        self._require_other_user(actor, seller_id)
        with self._reviews.lock_author(actor.user_id):
            self._require_active_actor(actor)
            self._require_seller(seller_id)
            self._validate_listing_context(listing_id, seller_id)
            now = utc_now()
            self._check_quota(actor.user_id, now)
            review, created = self._reviews.upsert(
                SellerReview(
                    seller_id=seller_id,
                    author_id=actor.user_id,
                    rating=rating,
                    listing_id=listing_id,
                    created_at=now,
                    updated_at=now,
                )
            )
            self._record(actor, ActivityType.REVIEW_SET, review, now)
            return review, created

    def remove_review(self, actor: CurrentUser, seller_id: UUID) -> None:
        self._require_other_user(actor, seller_id)
        with self._reviews.lock_author(actor.user_id):
            self._require_active_actor(actor)
            now = utc_now()
            self._check_quota(actor.user_id, now)
            review = self._reviews.delete(actor.user_id, seller_id, now)
            if review is None:
                raise SellerReviewNotFoundError("Оцінку не знайдено")
            self._record(actor, ActivityType.REVIEW_REMOVED, review, now)

    def summary(self, seller_id: UUID) -> SellerRating:
        counts = self._reviews.visible_distribution(seller_id)
        total = sum(counts.values())
        if total < self._min_count:
            return SellerRating(average=None, count=total, distribution=None)
        points = sum(rating * count for rating, count in counts.items())
        distribution = {
            rating: counts.get(rating, 0)
            for rating in range(MIN_RATING, MAX_RATING + 1)
        }
        return SellerRating(points / total, total, distribution)

    def get_rating(
        self, seller_id: UUID, viewer: CurrentUser | None
    ) -> tuple[SellerRating, int | None]:
        self._require_seller(seller_id)
        summary = self.summary(seller_id)
        own_review = self._reviews.find(viewer.user_id, seller_id) if viewer else None
        return summary, own_review.rating if own_review is not None else None

    def list_for_moderation(
        self,
        actor: CurrentUser,
        seller_id: UUID | None,
        author_id: UUID | None,
        skip: int,
        limit: int,
    ) -> tuple[list[SellerReview], dict[UUID, ReviewAuthorStats]]:
        self._require_admin(actor)
        reviews = self._reviews.list_reviews(seller_id, author_id, skip, limit)
        author_ids = {review.author_id for review in reviews}
        stats = self._reviews.author_stats(author_ids, utc_now() - REVIEW_WINDOW)
        # A concurrent deletion can remove an author's last review after pagination.
        return reviews, dict.fromkeys(author_ids, ReviewAuthorStats(0, 0, 0)) | stats

    def moderate(
        self, actor: CurrentUser, review_id: UUID, *, hide_reason: str | None
    ) -> SellerReview:
        self._require_admin(actor)
        reason = (
            normalize_moderation_reason(hide_reason)
            if hide_reason is not None
            else None
        )
        status = SellerReviewStatus.HIDDEN if reason else SellerReviewStatus.VISIBLE
        with self._reviews.lock_review(review_id) as review:
            if review is None:
                raise SellerReviewNotFoundError("Оцінку не знайдено")
            if review.status == status:
                return review

            now = utc_now()
            updated = replace(
                review,
                status=status,
                hidden_by=actor.user_id if reason else None,
                hidden_at=now if reason else None,
                hidden_reason=reason,
                updated_at=now,
            )
            self._reviews.save_moderation(updated)
            action = (
                ActivityType.REVIEW_HIDDEN if reason else ActivityType.REVIEW_RESTORED
            )
            self._record(actor, action, updated, now, reason)
            return updated

    def _require_seller(self, seller_id: UUID) -> None:
        if self._users.get_by_id(seller_id) is None:
            raise SellerReviewNotFoundError("Продавця не знайдено")

    def _require_active_actor(self, actor: CurrentUser) -> None:
        user = self._users.get_by_id(actor.user_id)
        if user is None or user.is_blocked:
            raise SellerReviewForbiddenError("Обліковий запис недоступний")

    @staticmethod
    def _require_other_user(actor: CurrentUser, seller_id: UUID) -> None:
        if actor.user_id == seller_id:
            raise SellerReviewForbiddenError("Не можна оцінювати себе")

    def _require_admin(self, actor: CurrentUser) -> None:
        if actor.role != UserRole.ADMIN:
            raise SellerReviewForbiddenError("Дія дозволена лише адміністраторам")
        self._require_active_actor(actor)

    def _validate_listing_context(
        self, listing_id: UUID | None, seller_id: UUID
    ) -> None:
        if listing_id is None:
            return
        listing = self._listings.get(listing_id)
        if listing is None:
            raise SellerReviewNotFoundError("Оголошення не знайдено")
        if listing.user_id != seller_id:
            raise InvalidSellerReviewContextError(
                "Оголошення не належить цьому продавцю"
            )

    def _check_quota(self, actor_id: UUID, now: datetime) -> None:
        if (
            self._events.count_review_mutations(actor_id, now - REVIEW_WINDOW)
            >= REVIEW_MUTATION_LIMIT
        ):
            raise SellerReviewRateLimitError(
                "Не більше 10 операцій з оцінками за 24 години"
            )

    def _record(
        self,
        actor: CurrentUser,
        action: ActivityType,
        review: SellerReview,
        now: datetime,
        reason: str | None = None,
    ) -> None:
        details = f"review_id={review.review_id}; seller_id={review.seller_id}"
        self._events.add(
            ActivityEvent(
                actor_id=actor.user_id,
                actor_role=actor.role,
                action_type=action,
                listing_id=review.listing_id,
                details=details,
                moderation_reason=reason,
                created_at=now,
            )
        )
