"""Модульні тести рейтингу, ліміту та журналу (ADR-004)."""

from dataclasses import replace
from datetime import datetime, timedelta, timezone
from uuid import uuid4

import pytest

from src.config import ConfigurationError, get_review_min_count_to_display
from src.domain.activity import ActivityEvent, ActivityType
from src.domain.exceptions import SellerReviewRateLimitError
from src.domain.seller_reviews import REVIEW_WINDOW, SellerReview, SellerReviewStatus
from src.domain.users import CurrentUser, User, UserRole
from src.repositories.seller_reviews import InMemorySellerReviewRepository
from src.repositories.users import InMemoryUserRepository
from src.services.seller_reviews import SellerReviewService

NOW = datetime(2026, 11, 16, 12, tzinfo=timezone.utc)


def _user(role: UserRole = UserRole.USER) -> tuple[User, CurrentUser]:
    user = User(uuid4(), uuid4(), f"{uuid4()}@ukma.edu.ua", "User", role=role)
    return user, CurrentUser(
        user.user_id,
        user.tenant_id,
        user.entra_object_id,
        user.email,
        user.display_name,
        role,
    )


@pytest.fixture
def reviews(activity_repository, listing_repository, monkeypatch):
    monkeypatch.setattr("src.services.seller_reviews.utc_now", lambda: NOW)
    repo = InMemorySellerReviewRepository()
    users = InMemoryUserRepository()
    service = SellerReviewService(
        repo, users, listing_repository, activity_repository, 3
    )

    def create_actor(role=UserRole.USER):
        user, current = _user(role)
        users.save(user)
        return current

    return service, repo, activity_repository, create_actor


def test_quota_is_rolling_per_author_and_counts_sets_and_deletions(reviews):
    """[FR-019] [TP-040] Десять операцій за 24 години, незалежно від продавця."""
    service, repository, events, actor = reviews
    author, seller, other_seller, other_author = (actor() for _ in range(4))
    for age, event_type in [
        (REVIEW_WINDOW, ActivityType.REVIEW_SET),
        (REVIEW_WINDOW + timedelta(seconds=1), ActivityType.REVIEW_REMOVED),
        (timedelta(hours=1), ActivityType.REVIEW_HIDDEN),
    ]:
        events.add(
            ActivityEvent(author.user_id, author.role, event_type, created_at=NOW - age)
        )

    for _ in range(4):
        service.set_review(author, seller.user_id, 4, None)
        service.remove_review(author, seller.user_id)
    service.set_review(author, seller.user_id, 5, None)
    service.set_review(author, other_seller.user_id, 1, None)
    with pytest.raises(SellerReviewRateLimitError):
        service.remove_review(author, seller.user_id)
    with pytest.raises(SellerReviewRateLimitError):
        service.set_review(author, other_seller.user_id, 2, None)
    assert repository.find(author.user_id, seller.user_id).rating == 5
    assert repository.find(author.user_id, other_seller.user_id).rating == 1
    assert events.count_review_mutations(author.user_id, NOW - REVIEW_WINDOW) == 10
    service.set_review(other_author, seller.user_id, 2, None)


def test_hidden_review_stays_hidden_on_update_and_restore_is_audited(reviews):
    """[FR-019] [FR-020] [FR-018] [TP-041] Повторний PUT зберігає стан модерації."""
    service, repository, events, actor = reviews
    seller, author = actor(), actor()
    admin = actor(UserRole.ADMIN)
    original, created = service.set_review(author, seller.user_id, 2, None)
    assert created
    hidden = service.moderate(
        admin, original.review_id, hide_reason="  Скоординована оцінка  "
    )
    assert hidden.hidden_by == admin.user_id
    assert hidden.hidden_at == NOW
    assert hidden.hidden_reason == "Скоординована оцінка"
    assert service.summary(seller.user_id).count == 0

    updated, created = service.set_review(author, seller.user_id, 5, None)
    assert not created
    assert updated == replace(hidden, rating=5)
    assert service.get_rating(seller.user_id, author)[1] == 5
    assert service.summary(seller.user_id).count == 0
    assert (
        service.moderate(admin, original.review_id, hide_reason="Інша причина")
        == updated
    )
    restored = service.moderate(admin, original.review_id, hide_reason=None)
    assert restored.status == SellerReviewStatus.VISIBLE
    assert (restored.hidden_by, restored.hidden_at, restored.hidden_reason) == (
        None,
        None,
        None,
    )
    assert repository.find(author.user_id, seller.user_id) == restored
    assert service.summary(seller.user_id).count == 1
    assert sorted(event.action_type for event in events.list_events(True)) == [
        ActivityType.REVIEW_HIDDEN,
        ActivityType.REVIEW_RESTORED,
    ]


@pytest.mark.parametrize("rating", [0, 6, True, 4.0])
def test_review_domain_validates_integer_stars(rating):
    """[FR-019] Домен приймає лише цілі зірки 1–5."""
    with pytest.raises(ValueError):
        SellerReview(uuid4(), uuid4(), rating)


def test_review_display_threshold_is_configurable(
    reviews, listing_repository, monkeypatch
):
    """[FR-019] [TP-042] Під порогом розкривається лише кількість."""
    service, repository, events, actor = reviews
    seller = actor()
    service.set_review(actor(), seller.user_id, 2, None)
    service.set_review(actor(), seller.user_id, 4, None)
    monkeypatch.delenv("REVIEW_MIN_COUNT_TO_DISPLAY", raising=False)
    assert get_review_min_count_to_display() == 1
    assert service.summary(seller.user_id).average is None
    monkeypatch.setenv("REVIEW_MIN_COUNT_TO_DISPLAY", "3")
    strict_service = SellerReviewService(
        repository,
        InMemoryUserRepository(),
        listing_repository,
        events,
        get_review_min_count_to_display(),
    )
    assert strict_service.summary(seller.user_id).average is None
    monkeypatch.setenv("REVIEW_MIN_COUNT_TO_DISPLAY", "2")
    custom_service = SellerReviewService(
        repository,
        InMemoryUserRepository(),
        listing_repository,
        events,
        get_review_min_count_to_display(),
    )
    assert custom_service.summary(seller.user_id).average == 3.0


@pytest.mark.parametrize("raw", ["", "0", "-1", "2.5"])
def test_review_display_threshold_rejects_invalid_values(raw, monkeypatch):
    """[FR-019] Некоректний поріг не можна непомітно застосувати."""
    monkeypatch.setenv("REVIEW_MIN_COUNT_TO_DISPLAY", raw)
    with pytest.raises(ConfigurationError, match="REVIEW_MIN_COUNT_TO_DISPLAY"):
        get_review_min_count_to_display()
