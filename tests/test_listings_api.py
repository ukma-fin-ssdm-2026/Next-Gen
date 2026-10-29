"""HTTP-тести каталогу та контролів безпеки TM-02 / TM-05."""

import io
from uuid import uuid4

from PIL import Image
import pytest
from fastapi.testclient import TestClient

from src.domain.listings import SEED_LISTING_ID, SEED_OWNER_ID, WITHDRAWN_LISTING_ID


def _make_dummy_jpeg(w: int = 100, h: int = 100, color=(255, 0, 0)) -> bytes:
    im = Image.new("RGB", (w, h), color)
    buf = io.BytesIO()
    im.save(buf, format="JPEG")
    return buf.getvalue()


def _make_dummy_png(w: int = 100, h: int = 100, color=(0, 255, 0)) -> bytes:
    im = Image.new("RGB", (w, h), color)
    buf = io.BytesIO()
    im.save(buf, format="PNG")
    return buf.getvalue()


def _make_dummy_webp(w: int = 100, h: int = 100, color=(0, 0, 255)) -> bytes:
    im = Image.new("RGB", (w, h), color)
    buf = io.BytesIO()
    im.save(buf, format="WEBP")
    return buf.getvalue()


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
    """[TP-002] [FR-002] Створення оголошення без actor_id повертає HTTP 401."""
    response = client.post(
        "/api/v1/listings",
        json=listing_payload,
    )
    assert response.status_code == 401


def test_patch_foreign_listing_is_403(client: TestClient) -> None:
    """[TP-009] [FR-003] Редагування чужого оголошення повертає HTTP 403."""
    response = client.patch(
        f"/api/v1/listings/{SEED_LISTING_ID}",
        headers={"X-Actor-Id": str(uuid4())},
        json={"title": "Спроба зламати чуже оголошення"},
    )
    assert response.status_code == 403
    assert "contact" not in response.json() or "detail" in response.json()


def test_owner_patch_updates_title_and_hides_contact(client: TestClient) -> None:
    """[TP-008] [FR-003] [SEC-002] PATCH оновлює назву та не повертає контакт."""
    response = client.patch(
        f"/api/v1/listings/{SEED_LISTING_ID}",
        headers={"X-Actor-Id": str(SEED_OWNER_ID)},
        json={"title": "Худі НаУКМА, розмір M"},
    )
    assert response.status_code == 200
    body = response.json()
    assert "contact" not in body
    assert body["title"] == "Худі НаУКМА, розмір M"


def test_patch_with_explicit_null_is_422(client: TestClient) -> None:
    """[TP-008] [FR-003] PATCH з невалідним null-значенням повертає 422."""
    response = client.patch(
        f"/api/v1/listings/{SEED_LISTING_ID}",
        headers={"X-Actor-Id": str(SEED_OWNER_ID)},
        json={"title": None},
    )
    assert response.status_code == 422


def test_delete_marks_withdrawn_and_hides_from_public(client: TestClient) -> None:
    """[TP-006] [FR-004]
    Зняття оголошення власником повертає 204 та приховує з каталогу.
    """
    response = client.delete(
        f"/api/v1/listings/{SEED_LISTING_ID}",
        headers={"X-Actor-Id": str(SEED_OWNER_ID)},
    )
    assert response.status_code == 204

    get_res = client.get(f"/api/v1/listings/{SEED_LISTING_ID}")
    assert get_res.status_code == 404

    list_res = client.get("/api/v1/listings")
    ids = {item["id"] for item in list_res.json()}
    assert str(SEED_LISTING_ID) not in ids


def test_delete_foreign_listing_is_403_and_preserves_listing(
    client: TestClient,
) -> None:
    """[TP-007] [FR-004]
    Спроба зняти чуже оголошення повертає 403 та зберігає оголошення.
    """
    before = client.get(f"/api/v1/listings/{SEED_LISTING_ID}")
    assert before.status_code == 200

    response = client.delete(
        f"/api/v1/listings/{SEED_LISTING_ID}",
        headers={"X-Actor-Id": str(uuid4())},
    )
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
) -> None:
    """[TP-003] [FR-008] Каталог підтримує сортування від найстаріших (sort=oldest)."""
    created = client.post(
        "/api/v1/listings",
        headers={"X-Actor-Id": str(SEED_OWNER_ID)},
        json=listing_payload,
    )
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
    """[TP-011] [FR-005] [SEC-001] GET /listings/my без актора повертає 401."""
    response = client.get("/api/v1/listings/my")
    assert response.status_code == 401


def test_get_my_listings_returns_active_and_withdrawn_for_owner(
    client: TestClient,
) -> None:
    """[TP-011] [FR-005] [SEC-001]
    GET /api/v1/listings/my повертає всі оголошення власника.
    """
    response = client.get(
        "/api/v1/listings/my",
        headers={"X-Actor-Id": str(SEED_OWNER_ID)},
    )
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
    seller = login_as()
    upload_res = client.post(
        "/api/v1/listings/images",
        files=[
            ("files", ("test1.jpg", _make_dummy_jpeg(100, 100), "image/jpeg")),
            ("files", ("test2.png", _make_dummy_png(150, 150), "image/png")),
        ],
    )
    assert upload_res.status_code == 201
    uploaded_keys = [item["storage_key"] for item in upload_res.json()]

    payload = {
        **listing_payload,
        "condition": "NEW",
        "image_urls": uploaded_keys,
    }
    created = client.post(
        "/api/v1/listings",
        headers={"X-Actor-Id": str(seller.user_id)},
        json=payload,
    )
    assert created.status_code == 201
    body = created.json()
    assert body["condition"] == "NEW"
    assert len(body["images"]) == 2
    assert body["images"][0]["display_order"] == 0
    assert body["images"][1]["display_order"] == 1

    up_new = client.post(
        "/api/v1/listings/images",
        files=[
            ("files", ("new.webp", _make_dummy_webp(200, 200), "image/webp")),
        ],
    )
    assert up_new.status_code == 201
    new_key = up_new.json()[0]["storage_key"]

    patched = client.patch(
        f"/api/v1/listings/{body['id']}",
        headers={"X-Actor-Id": str(seller.user_id)},
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
) -> None:
    """[TP-002] [FR-002] Невалідний URL фотографії відхиляється HTTP 422."""
    payload = {
        **listing_payload,
        "image_urls": ["ftp://invalid-scheme.example.com/photo.jpg"],
    }
    response = client.post(
        "/api/v1/listings",
        headers={"X-Actor-Id": str(SEED_OWNER_ID)},
        json=payload,
    )
    detail = response.json()["detail"]
    assert detail[0]["loc"] == ["body", "image_urls"]


def test_create_listing_rejects_empty_images_list_with_422(
    client: TestClient,
    listing_payload: dict[str, object],
) -> None:
    """[TP-002] [FR-002] Порожній список зображень відхиляється HTTP 422."""
    payload = {**listing_payload, "image_urls": []}
    response = client.post(
        "/api/v1/listings",
        headers={"X-Actor-Id": str(SEED_OWNER_ID)},
        json=payload,
    )
    assert response.status_code == 422


def test_patch_listing_failed_image_validation_preserves_state(
    client: TestClient,
) -> None:
    """[TP-008] [FR-003] Помилка валідації фото при PATCH зберігає стан оголошення."""
    before = client.get(f"/api/v1/listings/{SEED_LISTING_ID}").json()

    response = client.patch(
        f"/api/v1/listings/{SEED_LISTING_ID}",
        headers={"X-Actor-Id": str(SEED_OWNER_ID)},
        json={
            "title": "Не має зберегтися при помилці фото",
            "image_urls": ["ftp://invalid-scheme.example.com/photo.jpg"],
        },
    )
    assert response.status_code == 422

    after = client.get(f"/api/v1/listings/{SEED_LISTING_ID}").json()
    assert after == before
    assert response.status_code == 422


def test_create_listing_with_unknown_category_returns_400(
    client: TestClient,
    listing_payload: dict[str, object],
) -> None:
    """[TP-002] [FR-002] [FR-012]
    Створення оголошення з неіснуючою категорією повертає 400.
    """
    payload = {**listing_payload, "category_id": str(uuid4())}
    response = client.post(
        "/api/v1/listings",
        headers={"X-Actor-Id": str(SEED_OWNER_ID)},
        json=payload,
    )
    assert response.status_code == 400
    assert "не існує або була деактивована" in response.json()["detail"]


def test_create_listing_with_deactivated_category_returns_400(
    client: TestClient,
    listing_payload: dict[str, object],
) -> None:
    """[TP-002] [FR-002] [FR-012]
    Створення оголошення з деактивованою категорією відхиляється.
    """
    from src.api.deps import require_current_user
    from src.api.main import app
    from src.domain.users import CurrentUser, UserRole

    admin = CurrentUser(
        user_id=SEED_OWNER_ID,
        tenant_id=uuid4(),
        entra_object_id=uuid4(),
        email="admin@ukma.edu.ua",
        display_name="Admin",
        role=UserRole.ADMIN,
    )
    app.dependency_overrides[require_current_user] = lambda: admin
    cat_id = str(listing_payload["category_id"])
    patch_res = client.patch(
        f"/api/v1/categories/{cat_id}",
        json={"is_active": False},
    )
    assert patch_res.status_code == 200

    try:
        response = client.post(
            "/api/v1/listings",
            headers={"X-Actor-Id": str(SEED_OWNER_ID)},
            json=listing_payload,
        )
        assert response.status_code == 400
        assert "не існує або була деактивована" in response.json()["detail"]
    finally:
        client.patch(
            f"/api/v1/categories/{cat_id}",
            json={"is_active": True},
        )
        app.dependency_overrides.pop(require_current_user, None)
