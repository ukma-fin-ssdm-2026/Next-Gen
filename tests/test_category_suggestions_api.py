"""Інтеграційні API-тести пропозицій категорій та їх модерації (FR-015 / US-010)."""

from uuid import uuid4

from fastapi.testclient import TestClient

from src.domain.listings import OTHER_CATEGORY_ID, SEED_IMAGE_URL
from src.domain.users import UserRole
from tests.conftest import LoginAs


def test_create_listing_with_suggested_category_and_approve_flow(
    client: TestClient,
    login_as: LoginAs,
) -> None:
    """[TP-026] [TP-027] [TP-028] [FR-015] [US-010] Наскрізний сценарій схвалення."""
    seller = login_as(role=UserRole.USER)
    create_resp = client.post(
        "/api/v1/listings",
        json={
            "title": "Укулеле сопрано",
            "description": "Чохол у комплекті",
            "price": 1200.0,
            "contact": "@ukulele_ukma",
            "image_urls": [SEED_IMAGE_URL],
            "suggested_category_name": "Музичні інструменти",
        },
    )
    assert create_resp.status_code == 201
    created_data = create_resp.json()
    listing_id = created_data["id"]
    assert created_data["category_id"] == str(OTHER_CATEGORY_ID)
    assert created_data["suggested_category_name"] == "Музичні інструменти"

    # Публічний перегляд оголошення не розкриває suggested_category_name або контактів
    pub_resp = client.get(f"/api/v1/listings/{listing_id}")
    assert pub_resp.status_code == 200
    assert "suggested_category_name" not in pub_resp.json()
    assert "contact" not in pub_resp.json()

    # Звичайний користувач отримує 403 при спробі переглянути чергу пропозицій
    assert client.get("/api/v1/category-suggestions").status_code == 403
    assert (
        client.post(f"/api/v1/category-suggestions/{uuid4()}/approve").status_code
        == 403
    )

    # Адміністратор бачить пропозицію в черзі з listings_count = 1 і схвалює її
    admin = login_as(role=UserRole.ADMIN)
    queue_resp = client.get("/api/v1/category-suggestions?status=PENDING")
    assert queue_resp.status_code == 200
    queue = queue_resp.json()
    assert len(queue) == 1
    suggestion_id = queue[0]["suggestion_id"]
    assert queue[0]["listings_count"] == 1
    assert queue[0]["proposer_id"] == str(seller.user_id)

    approve_resp = client.post(
        f"/api/v1/category-suggestions/{suggestion_id}/approve",
        json={"name": "Музичні інструменти"},
    )
    assert approve_resp.status_code == 200
    approved_data = approve_resp.json()
    new_category_id = approved_data["category_id"]
    assert approved_data["status"] == "APPROVED"
    assert approved_data["reviewed_by"] == str(admin.user_id)
    assert new_category_id is not None

    # Нова категорія з'явилася в GET /api/v1/categories, а оголошення перейшло до неї
    cats_resp = client.get("/api/v1/categories")
    assert any(c["id"] == new_category_id for c in cats_resp.json())
    assert (
        client.get(f"/api/v1/listings/{listing_id}").json()["category_id"]
        == new_category_id
    )


def test_standalone_suggestion_reject_duplicates_quota_and_spoofing(
    client: TestClient,
    login_as: LoginAs,
) -> None:
    """[TP-026] [TP-027] [TP-028] [FR-015] [US-010] Відхилення, дублікати та квота."""
    # Анонімний запит -> 401 навіть із заголовком X-Actor-Id
    anon_resp = client.post(
        "/api/v1/category-suggestions",
        headers={"X-Actor-Id": str(uuid4())},
        json={"name": "Фототехніка"},
    )
    assert anon_resp.status_code == 401

    seller = login_as(role=UserRole.USER)
    spoofed_id = uuid4()
    resp1 = client.post(
        "/api/v1/category-suggestions",
        headers={"X-Actor-Id": str(spoofed_id)},
        json={
            "name": "Фототехніка",
            "proposer_id": str(spoofed_id),
            "role": "ADMIN",
        },
    )
    assert resp1.status_code == 201
    assert resp1.json()["proposer_id"] == str(seller.user_id)
    suggestion_id = resp1.json()["suggestion_id"]

    # Дублікат існуючої категорії (409) та дублікат PENDING (409)
    dup_existing = client.post("/api/v1/category-suggestions", json={"name": "  ІНШЕ "})
    assert dup_existing.status_code == 409
    assert str(OTHER_CATEGORY_ID) in dup_existing.json()["detail"]

    dup_pending = client.post(
        "/api/v1/category-suggestions", json={"name": "фототехніка"}
    )
    assert dup_pending.status_code == 409

    # Квота: максимум 3 PENDING на одного користувача, 4-та повертає 429
    assert (
        client.post(
            "/api/v1/category-suggestions", json={"name": "Настільні ігри"}
        ).status_code
        == 201
    )
    assert (
        client.post(
            "/api/v1/category-suggestions", json={"name": "Туризм і кемпінг"}
        ).status_code
        == 201
    )
    assert (
        client.post(
            "/api/v1/category-suggestions", json={"name": "Рослини та декор"}
        ).status_code
        == 429
    )

    # Валідація назви (422) та створення оголошення без категорії (422)
    assert (
        client.post("/api/v1/category-suggestions", json={"name": "А"}).status_code
        == 422
    )
    assert (
        client.post(
            "/api/v1/listings",
            json={
                "title": "Товар без категорії",
                "description": "Опис",
                "price": 50.0,
                "contact": "@user",
                "image_urls": [SEED_IMAGE_URL],
            },
        ).status_code
        == 422
    )

    # Відхилення: коротка причина -> 422, валідна -> 200, повторне -> 409
    login_as(role=UserRole.ADMIN)
    assert (
        client.post(
            f"/api/v1/category-suggestions/{suggestion_id}/reject",
            json={"reason": "Ні"},
        ).status_code
        == 422
    )
    reject_resp = client.post(
        f"/api/v1/category-suggestions/{suggestion_id}/reject",
        json={"reason": "Входить до категорії Електроніка та техніка"},
    )
    assert reject_resp.status_code == 200
    assert reject_resp.json()["status"] == "REJECTED"

    assert (
        client.post(
            f"/api/v1/category-suggestions/{suggestion_id}/reject",
            json={"reason": "Повторне відхилення"},
        ).status_code
        == 409
    )
    assert (
        client.post(
            f"/api/v1/category-suggestions/{uuid4()}/reject",
            json={"reason": "Неіснуюча пропозиція"},
        ).status_code
        == 404
    )

    # Заблокований користувач не може подати пропозицію (403)
    login_as(role=UserRole.USER, is_blocked=True)
    assert (
        client.post(
            "/api/v1/category-suggestions", json={"name": "Нова категорія"}
        ).status_code
        == 403
    )
