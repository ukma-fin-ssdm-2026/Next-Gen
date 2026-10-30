"""HTTP-тести каталогу та контролів безпеки SEC-001 / TM-02 / TM-05."""

from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from src.domain.listings import SEED_LISTING_ID, SEED_OWNER_ID, WITHDRAWN_LISTING_ID
from src.domain.users import UserRole
from tests.conftest import make_dummy_jpeg, make_dummy_png, make_dummy_webp


def test_health(client: TestClient) -> None:
    """[TP-003] [FR-006] Healthcheck endpoint перевірки працездатності сервісу."""
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"


def test_public_list_omits_contact(client: TestClient) -> None:
    """[TP-003] [FR-006] [SEC-002] Публічний перегляд каталогу маскує контакти."""
    response = client.get("/api/v1/listings")
    assert response.status_code == 200
    payload = response.json()
    assert payload
    for item in payload:
        assert "contact" not in item
        assert item["status"] == "ACTIVE"


def test_public_detail_omits_contact(client: TestClient) -> None:
    """[TP-003] [FR-006] [SEC-002] Публічний перегляд деталей маскує контакти."""
    response = client.get(f"/api/v1/listings/{SEED_LISTING_ID}")
    assert response.status_code == 200
    assert "contact" not in response.json()


def test_withdrawn_listing_not_in_catalog(client: TestClient) -> None:
    """[TP-005] [FR-004] [FR-006] Зняті оголошення відсутні в каталозі."""
    response = client.get("/api/v1/listings")
    ids = {item["id"] for item in response.json()}
    assert str(SEED_LISTING_ID) in ids
    assert "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee" not in ids


def test_search_query(client: TestClient) -> None:
    """[TP-003] [FR-007] Пошук оголошень за ключовим словом q."""
    response = client.get("/api/v1/listings", params={"q": "худі"})
    assert response.status_code == 200
    assert len(response.json()) == 1


def test_create_without_actor_is_401(
    client: TestClient,
    listing_payload: dict[str, object],
) -> None:
    """[TP-002] [FR-002] Створення оголошення без сесії повертає HTTP 401."""
    response = client.post(
        "/api/v1/listings",
        json=listing_payload,
    )
    assert response.status_code == 401


def test_create_and_patch_accept_empty_description(
    client: TestClient,
    listing_payload: dict[str, object],
    login_as,
) -> None:
    """[TP-001] [TP-008] [FR-002] [FR-003]
    Опис оголошення є необов'язковим під час створення і редагування.
    """
    login_as(user_id=SEED_OWNER_ID)
    payload = {**listing_payload}
    payload.pop("description")

    created = client.post("/api/v1/listings", json=payload)

    assert created.status_code == 201
    assert created.json()["description"] == ""

    patched = client.patch(
        f"/api/v1/listings/{SEED_LISTING_ID}",
        json={"description": ""},
    )
    assert patched.status_code == 200
    assert patched.json()["description"] == ""


def test_x_actor_id_without_session_is_rejected_with_401(
    client: TestClient,
    listing_payload: dict[str, object],
) -> None:
    """[TP-002] [SEC-001] [TM-02]
    Заголовок X-Actor-Id без серверної сесії Microsoft не приймається (401).
    """
    spoofed = {"X-Actor-Id": str(SEED_OWNER_ID)}
    assert (
        client.post(
            "/api/v1/listings", headers=spoofed, json=listing_payload
        ).status_code
        == 401
    )
    assert (
        client.patch(
            f"/api/v1/listings/{SEED_LISTING_ID}",
            headers=spoofed,
            json={"title": "Підміна заголовка"},
        ).status_code
        == 401
    )
    assert (
        client.delete(
            f"/api/v1/listings/{SEED_LISTING_ID}",
            headers=spoofed,
        ).status_code
        == 401
    )
    assert client.get("/api/v1/listings/my", headers=spoofed).status_code == 401


def test_x_actor_id_cannot_spoof_owner_when_logged_in_as_another_user(
    client: TestClient,
    listing_payload: dict[str, object],
    login_as,
) -> None:
    """[TP-009] [SEC-001] [TM-02]
    Навіть за наявності сесії клієнтський X-Actor-Id ігнорується на користь сесії.
    """
    user_b = login_as()
    spoofed_owner = {"X-Actor-Id": str(SEED_OWNER_ID)}

    created = client.post(
        "/api/v1/listings",
        headers=spoofed_owner,
        json=listing_payload,
    )
    assert created.status_code == 201
    assert created.json()["user_id"] == str(user_b.user_id)

    patch_foreign = client.patch(
        f"/api/v1/listings/{SEED_LISTING_ID}",
        headers=spoofed_owner,
        json={"title": "Спроба підмінити власника через X-Actor-Id"},
    )
    assert patch_foreign.status_code == 403


def test_patch_foreign_listing_is_403(client: TestClient, login_as) -> None:
    """[TP-009] [FR-003] Редагування чужого оголошення повертає HTTP 403."""
    login_as()
    response = client.patch(
        f"/api/v1/listings/{SEED_LISTING_ID}",
        json={"title": "Спроба зламати чуже оголошення"},
    )
    assert response.status_code == 403
    assert "contact" not in response.json() or "detail" in response.json()


def test_owner_patch_updates_title_and_hides_contact(
    client: TestClient,
    login_as,
) -> None:
    """[TP-008] [FR-003] [SEC-002] PATCH оновлює назву та не повертає контакт."""
    login_as(user_id=SEED_OWNER_ID)
    response = client.patch(
        f"/api/v1/listings/{SEED_LISTING_ID}",
        json={"title": "Худі НаУКМА, розмір M"},
    )
    assert response.status_code == 200
    body = response.json()
    assert "contact" not in body
    assert body["title"] == "Худі НаУКМА, розмір M"


def test_patch_with_explicit_null_is_422(client: TestClient, login_as) -> None:
    """[TP-008] [FR-003] PATCH з невалідним null-значенням повертає 422."""
    login_as(user_id=SEED_OWNER_ID)
    response = client.patch(
        f"/api/v1/listings/{SEED_LISTING_ID}",
        json={"title": None},
    )
    assert response.status_code == 422


def test_delete_marks_withdrawn_and_hides_from_public(
    client: TestClient,
    login_as,
) -> None:
    """[TP-006] [FR-004]
    Зняття оголошення власником повертає 204 та приховує з каталогу.
    """
    login_as(user_id=SEED_OWNER_ID)
    response = client.delete(f"/api/v1/listings/{SEED_LISTING_ID}")
    assert response.status_code == 204

    get_res = client.get(f"/api/v1/listings/{SEED_LISTING_ID}")
    assert get_res.status_code == 404

    list_res = client.get("/api/v1/listings")
    ids = {item["id"] for item in list_res.json()}
    assert str(SEED_LISTING_ID) not in ids


def test_delete_foreign_listing_is_403_and_preserves_listing(
    client: TestClient,
    login_as,
) -> None:
    """[TP-007] [FR-004]
    Спроба зняти чуже оголошення повертає 403 та зберігає оголошення.
    """
    before = client.get(f"/api/v1/listings/{SEED_LISTING_ID}")
    assert before.status_code == 200

    login_as()
    response = client.delete(f"/api/v1/listings/{SEED_LISTING_ID}")
    assert response.status_code == 403

    after = client.get(f"/api/v1/listings/{SEED_LISTING_ID}")
    assert after.status_code == 200
    assert after.json() == before.json()

    catalog = client.get("/api/v1/listings")
    assert catalog.status_code == 200
    assert str(SEED_LISTING_ID) in {item["id"] for item in catalog.json()}


def test_filter_by_price_range_api(client: TestClient) -> None:
    """[TP-004] [FR-008] Фільтрація оголошень за діапазоном цін через API."""
    res = client.get(
        "/api/v1/listings", params={"min_price": 100.0, "max_price": 200.0}
    )
    assert res.status_code == 200
    assert len(res.json()) == 1

    res_empty = client.get("/api/v1/listings", params={"min_price": 200.0})
    assert res_empty.status_code == 200
    assert len(res_empty.json()) == 0


def test_catalog_rejects_inverted_price_range(client: TestClient) -> None:
    """[TP-004] [FR-008]
    Регресійний тест: API повертає HTTP 422, якщо min_price > max_price.
    """
    res = client.get(
        "/api/v1/listings", params={"min_price": 200.0, "max_price": 100.0}
    )
    assert res.status_code == 422
    payload = res.json()
    assert isinstance(payload["detail"], list)
    assert payload["detail"][0]["loc"] == ["query", "min_price"]
    assert "min_price" in payload["detail"][0]["msg"]
    assert "не може перевищувати max_price" in payload["detail"][0]["msg"]
    assert payload["detail"][0]["type"] == "value_error"


def test_catalog_accepts_oldest_sort_order(
    client: TestClient,
    listing_payload: dict[str, object],
    login_as,
) -> None:
    """[TP-003] [FR-008] Каталог підтримує сортування від найстаріших (sort=oldest)."""
    login_as(user_id=SEED_OWNER_ID)
    created = client.post("/api/v1/listings", json=listing_payload)
    assert created.status_code == 201

    response = client.get("/api/v1/listings", params={"sort": "oldest"})

    assert response.status_code == 200
    assert response.json()[0]["id"] == str(SEED_LISTING_ID)


@pytest.mark.parametrize(
    "params",
    [
        {"skip": -1},
        {"limit": 0},
        {"limit": 101},
        {"q": ""},
        {"min_price": -0.01},
        {"sort": "unsupported"},
    ],
)
def test_catalog_rejects_invalid_query_boundaries(
    client: TestClient,
    params: dict[str, object],
) -> None:
    """[TP-003] [FR-006] [FR-008] Некоректні параметри фільтрів повертають HTTP 422."""
    response = client.get("/api/v1/listings", params=params)
    assert response.status_code == 422


def test_get_my_listings_requires_actor(client: TestClient) -> None:
    """[TP-011] [FR-005] [SEC-001] GET /listings/my без сесії повертає 401."""
    response = client.get("/api/v1/listings/my")
    assert response.status_code == 401


def test_get_my_listings_returns_active_and_withdrawn_for_owner(
    client: TestClient,
    login_as,
) -> None:
    """[TP-011] [FR-005] [SEC-001]
    GET /api/v1/listings/my повертає всі оголошення власника.
    """
    login_as(user_id=SEED_OWNER_ID)
    response = client.get("/api/v1/listings/my")
    assert response.status_code == 200
    payload = response.json()
    ids = {item["id"] for item in payload}
    statuses = {item["status"] for item in payload}

    assert ids == {str(SEED_LISTING_ID), str(WITHDRAWN_LISTING_ID)}
    assert statuses == {"ACTIVE", "WITHDRAWN"}
    assert all("contact" not in item for item in payload)


def test_create_and_patch_listing_with_images_and_condition(
    client: TestClient,
    listing_payload: dict[str, object],
    login_as,
) -> None:
    """[TP-001] [FR-002] [FR-003] Створення та PATCH оголошення з фотографіями."""
    login_as()
    upload_res = client.post(
        "/api/v1/listings/images",
        files=[
            ("files", ("test1.jpg", make_dummy_jpeg(100, 100), "image/jpeg")),
            ("files", ("test2.png", make_dummy_png(150, 150), "image/png")),
        ],
    )
    assert upload_res.status_code == 201
    uploaded_keys = [item["storage_key"] for item in upload_res.json()]

    payload = {
        **listing_payload,
        "condition": "NEW",
        "image_urls": uploaded_keys,
    }
    created = client.post("/api/v1/listings", json=payload)
    assert created.status_code == 201
    body = created.json()
    assert body["condition"] == "NEW"
    assert len(body["images"]) == 2
    assert body["images"][0]["display_order"] == 0
    assert body["images"][1]["display_order"] == 1

    up_new = client.post(
        "/api/v1/listings/images",
        files=[
            ("files", ("new.webp", make_dummy_webp(200, 200), "image/webp")),
        ],
    )
    assert up_new.status_code == 201
    new_key = up_new.json()[0]["storage_key"]

    patched = client.patch(
        f"/api/v1/listings/{body['id']}",
        json={
            "condition": "USED",
            "image_urls": [new_key],
        },
    )
    assert patched.status_code == 200
    patched_body = patched.json()
    assert patched_body["condition"] == "USED"
    assert len(patched_body["images"]) == 1
    assert new_key in patched_body["images"][0]["image_url"]


def test_create_listing_rejects_invalid_image_url_with_422(
    client: TestClient,
    listing_payload: dict[str, object],
    login_as,
) -> None:
    """[TP-002] [FR-002] Невалідний URL фотографії відхиляється HTTP 422."""
    login_as(user_id=SEED_OWNER_ID)
    payload = {
        **listing_payload,
        "image_urls": ["ftp://invalid-scheme.example.com/photo.jpg"],
    }
    response = client.post("/api/v1/listings", json=payload)
    assert response.status_code == 422
    detail = response.json()["detail"]
    assert detail[0]["loc"] == ["body", "image_urls"]


def test_create_listing_rejects_empty_images_list_with_422(
    client: TestClient,
    listing_payload: dict[str, object],
    login_as,
) -> None:
    """[TP-002] [FR-002] Порожній список зображень відхиляється HTTP 422."""
    login_as(user_id=SEED_OWNER_ID)
    payload = {**listing_payload, "image_urls": []}
    response = client.post("/api/v1/listings", json=payload)
    assert response.status_code == 422


def test_patch_listing_failed_image_validation_preserves_state(
    client: TestClient,
    login_as,
) -> None:
    """[TP-008] [FR-003] Помилка валідації фото при PATCH зберігає стан оголошення."""
    before = client.get(f"/api/v1/listings/{SEED_LISTING_ID}").json()
    login_as(user_id=SEED_OWNER_ID)

    response = client.patch(
        f"/api/v1/listings/{SEED_LISTING_ID}",
        json={
            "title": "Не має зберегтися при помилці фото",
            "image_urls": ["ftp://invalid-scheme.example.com/photo.jpg"],
        },
    )
    assert response.status_code == 422

    after = client.get(f"/api/v1/listings/{SEED_LISTING_ID}").json()
    assert after == before


def test_create_listing_with_unknown_category_returns_400(
    client: TestClient,
    listing_payload: dict[str, object],
    login_as,
) -> None:
    """[TP-002] [FR-002] [FR-012]
    Створення оголошення з неіснуючою категорією повертає 400.
    """
    login_as(user_id=SEED_OWNER_ID)
    payload = {**listing_payload, "category_id": str(uuid4())}
    response = client.post("/api/v1/listings", json=payload)
    assert response.status_code == 400
    assert "не існує або була деактивована" in response.json()["detail"]


def test_create_listing_with_deactivated_category_returns_400(
    client: TestClient,
    listing_payload: dict[str, object],
    login_as,
) -> None:
    """[TP-002] [FR-002] [FR-012]
    Створення оголошення з деактивованою категорією відхиляється.
    """
    login_as(role=UserRole.ADMIN, user_id=SEED_OWNER_ID)
    cat_id = str(listing_payload["category_id"])
    patch_res = client.patch(
        f"/api/v1/categories/{cat_id}",
        json={"is_active": False},
    )
    assert patch_res.status_code == 200

    try:
        response = client.post("/api/v1/listings", json=listing_payload)
        assert response.status_code == 400
        assert "не існує або була деактивована" in response.json()["detail"]
    finally:
        client.patch(
            f"/api/v1/categories/{cat_id}",
            json={"is_active": True},
        )


def test_price_upper_limit_is_enforced(
    client: TestClient,
    listing_payload: dict[str, object],
    login_as,
) -> None:
    """[TP-001] [FR-002] Ціна не може перевищувати 100 000 000 грн."""
    login_as(user_id=SEED_OWNER_ID)

    too_much = client.post(
        "/api/v1/listings", json={**listing_payload, "price": 100_000_000.01}
    )
    at_limit = client.post(
        "/api/v1/listings", json={**listing_payload, "price": 100_000_000}
    )
    filter_too_high = client.get("/api/v1/listings", params={"max_price": 1e12})

    assert too_much.status_code == 422
    assert at_limit.status_code == 201
    assert filter_too_high.status_code == 422
    patched = client.patch(
        f"/api/v1/listings/{at_limit.json()['id']}", json={"price": 100_000_001}
    )
    assert patched.status_code == 422


def test_catalog_accepts_price_sort_orders(client: TestClient) -> None:
    """[TP-004] [FR-008] API приймає сортування за ціною і відхиляє невідоме."""
    for order in ("price_asc", "price_desc", "newest", "oldest"):
        assert client.get("/api/v1/listings", params={"sort": order}).status_code == 200
    assert (
        client.get("/api/v1/listings", params={"sort": "cheapest"}).status_code == 422
    )


def test_listing_accepts_for_parts_condition(
    client: TestClient, login_as, listing_payload
) -> None:
    """[TP-001] [FR-002] Стан FOR_PARTS приймається, невідомий стан — 422."""
    login_as()
    created = client.post(
        "/api/v1/listings", json={**listing_payload, "condition": "FOR_PARTS"}
    )
    assert created.status_code == 201
    assert created.json()["condition"] == "FOR_PARTS"
    bad = client.post(
        "/api/v1/listings", json={**listing_payload, "condition": "BROKEN"}
    )
    assert bad.status_code == 422
