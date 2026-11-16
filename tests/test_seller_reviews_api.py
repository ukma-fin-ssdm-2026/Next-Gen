"""HTTP-контракт рейтингу, в тому числі автентифікація через cookie сесії."""

from dataclasses import replace
from uuid import uuid4

import pytest

from src.api.deps import (
    SESSION_COOKIE_NAME,
    get_seller_review_service,
    get_user_repository,
)
from src.api.main import app
from src.domain.users import UserRole
from src.repositories.seller_reviews import InMemorySellerReviewRepository
from src.services.seller_reviews import SellerReviewService

API = "/api/v1"


@pytest.fixture
def setup_reviews(
    client, login_as, listing_repository, activity_repository, monkeypatch
):
    users = app.dependency_overrides[get_user_repository]()
    repository = InMemorySellerReviewRepository()
    service = SellerReviewService(
        repository, users, listing_repository, activity_repository, 3
    )
    monkeypatch.setitem(
        app.dependency_overrides, get_seller_review_service, lambda: service
    )

    seller = login_as()
    public_listing = listing_repository.list_all()[0]
    listing = listing_repository.save(replace(public_listing, user_id=seller.user_id))
    client.cookies.clear()
    return seller, listing, repository


def _review_path(seller_id):
    return f"{API}/users/{seller_id}/review"


def _rating_path(seller_id):
    return f"{API}/users/{seller_id}/rating"


def test_review_writes_require_session_and_reject_blocked_users(
    client, login_as, setup_reviews
):
    """[FR-019] [SEC-001] [TP-039] Анонім та заблокований не можуть писати оцінки."""
    seller, _, repository = setup_reviews
    path = _review_path(seller.user_id)
    assert (
        client.put(
            path, json={"rating": 4}, headers={"X-Actor-Id": str(uuid4())}
        ).status_code
        == 401
    )
    assert client.delete(path).status_code == 401

    author = login_as()
    assert client.put(path, json={"rating": 4}).status_code == 201
    login_as(is_blocked=True, user_id=author.user_id)
    assert client.put(path, json={"rating": 5}).status_code == 403
    login_as(is_blocked=True, user_id=author.user_id)
    assert client.delete(path).status_code == 403
    assert repository.find(author.user_id, seller.user_id).rating == 4
    assert client.get(_rating_path(seller.user_id)).json()["count"] == 1


@pytest.mark.parametrize("rating", [0, 6, True, "4", 4.5])
def test_invalid_rating_does_not_create_review(client, login_as, setup_reviews, rating):
    """[FR-019] [TP-039] Оцінка має бути цілим числом 1–5."""
    seller, _, repository = setup_reviews
    author = login_as()
    assert (
        client.put(_review_path(seller.user_id), json={"rating": rating}).status_code
        == 422
    )
    assert repository.find(author.user_id, seller.user_id) is None


def test_review_checks_target_listing_and_session_author(
    client, login_as, setup_reviews
):
    """[FR-019] [SEC-001] [TP-039] Перевірка цілі й захист від підміни автора."""
    seller, listing, repository = setup_reviews
    other_user = login_as()
    author = login_as()
    path = _review_path(seller.user_id)
    assert (
        client.put(_review_path(author.user_id), json={"rating": 3}).status_code == 403
    )
    missing_id = uuid4()
    assert client.put(_review_path(missing_id), json={"rating": 3}).status_code == 404
    assert client.get(_rating_path(missing_id)).status_code == 404
    assert client.delete(path).status_code == 404
    assert (
        client.put(path, json={"rating": 3, "listing_id": str(uuid4())}).status_code
        == 404
    )
    foreign = client.put(
        _review_path(other_user.user_id),
        json={"rating": 3, "listing_id": str(listing.id)},
    )
    assert foreign.status_code == 422
    assert foreign.json()["detail"][0]["loc"] == ["body", "listing_id"]
    assert repository.find(author.user_id, other_user.user_id) is None
    for field, value in (
        ("author_id", str(other_user.user_id)),
        ("role", "ADMIN"),
        ("email", seller.email),
    ):
        assert client.put(path, json={"rating": 3, field: value}).status_code == 422
    assert repository.find(author.user_id, seller.user_id) is None

    response = client.put(path, json={"rating": 3, "listing_id": str(listing.id)})
    assert response.status_code == 201
    assert response.json()["listing_id"] == str(listing.id)
    assert repository.find(author.user_id, seller.user_id).author_id == author.user_id


def test_review_upsert_and_delete_have_correct_statuses_and_audit(
    client, login_as, setup_reviews
):
    """[FR-019] [FR-018] [TP-039] Створення 201, оновлення 200, видалення 204."""
    seller, _, repository = setup_reviews
    author = login_as()
    path = _review_path(seller.user_id)
    first = client.put(path, json={"rating": 3})
    second = client.put(path, json={"rating": 5})
    assert (first.status_code, second.status_code) == (201, 200)
    assert first.json()["review_id"] == second.json()["review_id"]
    assert first.json()["created_at"] == second.json()["created_at"]
    assert second.json()["rating"] == 5
    assert {"author_id", "email", "hidden_by"}.isdisjoint(second.json())
    deleted = client.delete(path)
    assert deleted.status_code == 204
    assert deleted.content == b""
    assert client.delete(path).status_code == 404
    assert repository.find(author.user_id, seller.user_id) is None

    login_as(UserRole.ADMIN)
    logs = client.get(f"{API}/admin/logs/users").json()
    assert [entry["action_type"] for entry in logs] == [
        "REVIEW_REMOVED",
        "REVIEW_SET",
        "REVIEW_SET",
    ]


def test_eleventh_review_mutation_returns_429(client, login_as, setup_reviews):
    """[FR-019] [TP-040] PUT та DELETE використовують спільний добовий ліміт."""
    seller, _, _ = setup_reviews
    login_as()
    path = _review_path(seller.user_id)
    for _ in range(5):
        assert client.put(path, json={"rating": 3}).status_code == 201
        assert client.delete(path).status_code == 204
    assert client.put(path, json={"rating": 3}).status_code == 429


def test_rating_returns_private_own_score_and_public_aggregate(
    client, login_as, setup_reviews
):
    """[FR-019] [TP-042] Агрегат не розкриває авторів, my_rating бачить його автор."""
    seller, listing, _ = setup_reviews
    path = _review_path(seller.user_id)
    aggregate_url = _rating_path(seller.user_id)
    assert client.get(aggregate_url).json() == {
        "average": None,
        "count": 0,
        "distribution": None,
    }
    for rating in (1, 3, 5):
        login_as()
        assert client.put(path, json={"rating": rating}).status_code == 201
        response = client.get(aggregate_url)
        assert response.headers["cache-control"] == "private, no-store"
        assert response.json()["my_rating"] == rating
        if rating < 5:
            assert response.json()["average"] is None
            assert response.json()["distribution"] is None
    public = {
        "average": 3.0,
        "count": 3,
        "distribution": {"1": 1, "2": 0, "3": 1, "4": 0, "5": 1},
    }
    login_as()  # A signed-in viewer without a review also receives only the aggregate.
    assert client.get(aggregate_url).json() == public
    client.cookies.set(SESSION_COOKIE_NAME, "expired-or-forged")
    assert client.get(aggregate_url).json() == public
    client.cookies.clear()
    assert client.get(aggregate_url).json() == public
    detail = client.get(f"{API}/listings/{listing.id}").json()
    assert detail["seller_rating"] == {"average": 3.0, "count": 3}
    assert "contact" not in detail


def test_list_responses_do_not_query_reviews_or_include_rating(
    client, login_as, setup_reviews, monkeypatch
):
    """[FR-019] [FR-006] [TP-042] Списки не запитують рейтинг."""
    seller, listing, _ = setup_reviews

    def unexpected_review_service():
        pytest.fail("Списковий маршрут викликав залежність рейтингу")

    monkeypatch.setitem(
        app.dependency_overrides, get_seller_review_service, unexpected_review_service
    )
    for params in ({}, {"q": listing.title}):
        result = client.get(f"{API}/listings", params=params).json()
        assert result and all("seller_rating" not in item for item in result)
    login_as(user_id=seller.user_id)
    mine = client.get(f"{API}/listings/my").json()
    assert mine and all("seller_rating" not in item for item in mine)
    login_as()
    assert client.post(f"{API}/favorites/{listing.id}").status_code == 201
    favorites = client.get(f"{API}/favorites").json()
    assert favorites and all("seller_rating" not in item for item in favorites)


def test_review_moderation_roles_filters_and_audit(client, login_as, setup_reviews):
    """[FR-020] [FR-018] [TP-041] Модерація й аудит лише для ADMIN."""
    seller, _, repository = setup_reviews
    path = _review_path(seller.user_id)
    for rating in (5, 4):
        login_as()
        assert client.put(path, json={"rating": rating}).status_code == 201
    author = login_as()
    review_id = client.put(path, json={"rating": 1}).json()["review_id"]
    admin_url = f"{API}/admin/reviews"
    hide = f"{admin_url}/{review_id}/hide"
    restore = f"{admin_url}/{review_id}/restore"
    reason = "Ознаки скоординованих оцінок"

    assert client.get(admin_url).status_code == 403
    assert client.post(hide, json={"reason": reason}).status_code == 403
    assert client.post(restore).status_code == 403
    client.cookies.clear()
    assert client.get(admin_url).status_code == 401
    assert client.post(hide, json={"reason": reason}).status_code == 401
    assert client.post(restore).status_code == 401

    admin = login_as(UserRole.ADMIN)
    assert (
        client.post(f"{admin_url}/{uuid4()}/hide", json={"reason": reason}).status_code
        == 404
    )
    assert client.post(f"{admin_url}/{uuid4()}/restore").status_code == 404
    assert client.post(hide, json={"reason": "     "}).status_code == 422
    assert client.post(hide, json={}).status_code == 422
    before = client.get(_rating_path(seller.user_id)).json()
    assert before["average"] == pytest.approx(10 / 3)
    hidden = client.post(hide, json={"reason": f"  {reason}  "})
    assert hidden.status_code == 200
    assert hidden.json()["status"] == "HIDDEN"
    assert hidden.json()["hidden_by"] == str(admin.user_id)
    assert hidden.json()["hidden_reason"] == reason
    assert hidden.json()["hidden_at"]
    aggregate = client.get(_rating_path(seller.user_id)).json()
    assert aggregate == {"average": None, "count": 2, "distribution": None}

    params = {"seller_id": str(seller.user_id), "author_id": str(author.user_id)}
    entries = client.get(admin_url, params=params).json()
    assert len(entries) == 1
    assert entries[0]["review_id"] == review_id
    assert entries[0]["author_id"] == str(author.user_id)
    assert entries[0]["seller_id"] == str(seller.user_id)
    assert entries[0]["author_stats"] == {
        "total_count": 1,
        "recent_count": 1,
        "recent_one_star_count": 1,
    }
    assert client.get(admin_url, params={**params, "skip": 1}).json() == []
    assert client.post(restore).json()["status"] == "VISIBLE"
    assert client.get(_rating_path(seller.user_id)).json() == before
    assert repository.find(author.user_id, seller.user_id).hidden_at is None
    logs = client.get(f"{API}/admin/logs/admins").json()
    assert [entry["action_type"] for entry in logs] == [
        "REVIEW_RESTORED",
        "REVIEW_HIDDEN",
    ]


@pytest.mark.parametrize("recreate_before_restore", [True, False])
def test_deleted_hidden_review_requires_admin_restore(
    client, login_as, setup_reviews, recreate_before_restore
):
    """[FR-020] [TP-041] Видалення не скидає приховування або причину в аудиті."""
    seller, _, _ = setup_reviews
    listing_path = _review_path(seller.user_id)
    rating_path = _rating_path(seller.user_id)
    author = login_as()
    review_id = client.put(listing_path, json={"rating": 1}).json()["review_id"]
    admin = login_as(UserRole.ADMIN)
    review_path = f"{API}/admin/reviews/{review_id}"
    reason = "я" * 499 + "!"
    assert (
        client.post(f"{review_path}/hide", json={"reason": reason}).status_code == 200
    )
    login_as(user_id=author.user_id)
    assert client.delete(listing_path).status_code == 204
    assert client.delete(listing_path).status_code == 404
    assert client.get(rating_path).json() == {
        "average": None,
        "count": 0,
        "distribution": None,
    }

    login_as(UserRole.ADMIN, user_id=admin.user_id)
    (row,) = client.get(f"{API}/admin/reviews").json()
    assert row["review_id"] == review_id
    assert row["status"] == "HIDDEN"
    assert row["deleted_at"] is not None
    assert row["author_stats"]["total_count"] == 0
    assert row["hidden_reason"] == reason

    if recreate_before_restore:
        login_as(user_id=author.user_id)
        response = client.put(listing_path, json={"rating": 5})
        assert response.status_code == 200
        assert response.json()["review_id"] == review_id
        assert response.json()["status"] == "HIDDEN"
        assert client.get(rating_path).json()["count"] == 0
        login_as(UserRole.ADMIN, user_id=admin.user_id)

    assert client.post(f"{review_path}/restore").status_code == 200
    assert client.get(rating_path).json()["count"] == int(recreate_before_restore)
    logs = client.get(f"{API}/admin/logs/admins").json()
    (hide,) = [log for log in logs if log["action_type"] == "REVIEW_HIDDEN"]
    assert hide["details"].endswith(f"; reason={reason}")

    if not recreate_before_restore:
        assert client.get(f"{API}/admin/reviews").json() == []
        login_as(user_id=author.user_id)
        assert client.delete(listing_path).status_code == 404
        first = client.put(listing_path, json={"rating": 5})
        assert first.status_code == 201
        assert first.json()["status"] == "VISIBLE"
