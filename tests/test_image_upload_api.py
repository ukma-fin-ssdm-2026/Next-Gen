"""Інтеграційні тести API завантаження фотографій та сесій (FR-002, TM-03, TM-08)."""

import io
from pathlib import Path

from PIL import Image
from fastapi.testclient import TestClient

from src.api.deps import category_service, get_image_storage, get_listing_service
from src.api.main import app
from src.domain.listings import SEED_CATEGORY_ID
from src.repositories.image_storage import LocalImageStorage
from src.services.listings import ListingService


def _make_jpeg_file(w: int = 120, h: int = 80, color=(100, 150, 200)) -> bytes:
    im = Image.new("RGB", (w, h), color)
    buf = io.BytesIO()
    im.save(buf, format="JPEG")
    return buf.getvalue()


def _make_png_file(w: int = 150, h: int = 100, color=(50, 100, 150)) -> bytes:
    im = Image.new("RGB", (w, h), color)
    buf = io.BytesIO()
    im.save(buf, format="PNG")
    return buf.getvalue()


def _make_heic_file(w: int = 160, h: int = 110) -> bytes:
    im = Image.new("RGB", (w, h), (180, 90, 45))
    buf = io.BytesIO()
    im.save(buf, format="HEIF")
    return buf.getvalue()


def test_upload_images_unauthorized_returns_401(client: TestClient) -> None:
    """[TP-023] [FR-002] [SEC-001]
    Завантаження зображень без автентифікованої сесії відхиляється кодом HTTP 401.
    """
    file_bytes = _make_jpeg_file()
    response = client.post(
        "/api/v1/listings/images",
        files=[("files", ("photo.jpg", file_bytes, "image/jpeg"))],
    )
    assert response.status_code == 401
    assert "потрібен вхід" in response.json()["detail"].lower()


def test_upload_images_blocked_user_returns_403(
    client: TestClient,
    login_as,
) -> None:
    """[TP-023] [FR-002] [SEC-001]
    Заблокований користувач отримує HTTP 403 при спробі завантаження.
    """
    login_as(is_blocked=True)
    file_bytes = _make_jpeg_file()
    response = client.post(
        "/api/v1/listings/images",
        files=[("files", ("photo.jpg", file_bytes, "image/jpeg"))],
    )
    assert response.status_code == 403


def test_upload_images_success(client: TestClient, login_as) -> None:
    """[TP-023] [FR-002]
    Успішне завантаження фотографій повертає HTTP 201 та валідні метадані.
    """
    login_as()
    files = [
        ("files", ("photo1.jpg", _make_jpeg_file(600, 400), "image/jpeg")),
        ("files", ("photo2.png", _make_png_file(800, 600), "image/png")),
        ("files", ("photo3.heic", _make_heic_file(400, 300), "image/heic")),
    ]
    response = client.post("/api/v1/listings/images", files=files)
    assert response.status_code == 201
    items = response.json()
    assert len(items) == 3

    for idx, item in enumerate(items):
        assert item["display_order"] == idx
        assert item["storage_key"].endswith(".webp")
        assert item["image_url"].startswith("/uploads/")
        assert item["thumbnail_url"].endswith("_thumb.webp")
        assert item["width"] > 0
        assert item["height"] > 0
        assert item["thumbnail_width"] > 0
        assert item["thumbnail_height"] > 0


def test_upload_images_rejects_empty_files_or_more_than_ten(
    client: TestClient,
    login_as,
) -> None:
    """[TP-023] [FR-002]
    Відхилення запиту з кількістю файлів поза діапазоном 1..10 (HTTP 422).
    """
    login_as()
    # 0 файлів
    res_empty = client.post("/api/v1/listings/images", files=[])
    assert res_empty.status_code == 422

    # 11 файлів
    too_many = [
        ("files", (f"p{i}.jpg", _make_jpeg_file(50, 50), "image/jpeg"))
        for i in range(11)
    ]
    res_many = client.post("/api/v1/listings/images", files=too_many)
    assert res_many.status_code == 422


def test_upload_images_rejects_corrupted_file_with_422(
    client: TestClient,
    login_as,
) -> None:
    """[TP-023] [FR-002] [TM-03]
    Відхилення пошкодженого файлу або невалідних байтів з HTTP 422.
    """
    login_as()
    corrupted = b"this is not a valid image content"
    response = client.post(
        "/api/v1/listings/images",
        files=[("files", ("corrupt.jpg", corrupted, "image/jpeg"))],
    )
    assert response.status_code == 422
    assert "detail" in response.json()


def test_get_uploaded_image_serves_webp(client: TestClient, login_as) -> None:
    """[TP-023] [FR-002]
    Отримання завантаженого зображення за ендпоінтом /uploads/{storage_key}.
    """
    login_as()
    upload_res = client.post(
        "/api/v1/listings/images",
        files=[("files", ("test.jpg", _make_jpeg_file(200, 200), "image/jpeg"))],
    )
    assert upload_res.status_code == 201
    key = upload_res.json()[0]["storage_key"]

    get_res = client.get(f"/uploads/{key}")
    assert get_res.status_code == 200
    assert get_res.headers["content-type"] == "image/webp"
    assert get_res.content.startswith(b"RIFF")


def test_get_uploaded_image_not_found(client: TestClient) -> None:
    """[TP-023] [FR-002] [TM-03]
    Запит неіснуючого або некоректного ключа повертає HTTP 404.
    """
    assert client.get("/uploads/nonexistent.webp").status_code == 404
    assert client.get("/uploads/../../secret.txt").status_code == 404


def test_full_listing_lifecycle_with_local_image_storage(
    client: TestClient,
    tmp_path: Path,
    listing_repository,
    favorite_repository,
    login_as,
) -> None:
    """[TP-023] [FR-002] [FR-003]
    Життєвий цикл оголошення після заміни in-memory на LocalImageStorage.
    """
    local_storage = LocalImageStorage(tmp_path)
    custom_service = ListingService(
        listing_repository,
        image_storage=local_storage,
        favorites=favorite_repository,
        category_validator=category_service.is_valid_category_id,
    )
    app.dependency_overrides[get_image_storage] = lambda: local_storage
    app.dependency_overrides[get_listing_service] = lambda: custom_service

    try:
        user = login_as()

        # 1. Завантаження двох зображень у LocalImageStorage
        up_res = client.post(
            "/api/v1/listings/images",
            files=[
                ("files", ("f1.jpg", _make_jpeg_file(400, 400), "image/jpeg")),
                ("files", ("f2.png", _make_png_file(500, 500), "image/png")),
            ],
        )
        assert up_res.status_code == 201
        keys = [it["storage_key"] for it in up_res.json()]
        assert (tmp_path / keys[0]).is_file()
        assert (tmp_path / keys[1]).is_file()

        # 2. Створення оголошення з цими ключами
        payload = {
            "title": "Зошит з конспектами",
            "description": "Зошит з повним курсом лекцій.",
            "price": 120.0,
            "category_id": str(SEED_CATEGORY_ID),
            "contact": "@student_notebook",
            "condition": "GOOD",
            "image_urls": keys,
        }
        create_res = client.post(
            "/api/v1/listings",
            headers={"X-Actor-Id": str(user.user_id)},
            json=payload,
        )
        assert create_res.status_code == 201
        listing_id = create_res.json()["id"]

        # 3. Завантаження нового фото та PATCH оновлення (заміна фото)
        up_new = client.post(
            "/api/v1/listings/images",
            files=[("files", ("f3.jpg", _make_jpeg_file(300, 300), "image/jpeg"))],
        )
        assert up_new.status_code == 201
        new_key = up_new.json()[0]["storage_key"]

        # Замінюємо: залишаємо keys[0], видаляємо keys[1], додаємо new_key
        patch_res = client.patch(
            f"/api/v1/listings/{listing_id}",
            headers={"X-Actor-Id": str(user.user_id)},
            json={"image_urls": [keys[0], new_key]},
        )
        assert patch_res.status_code == 200

        # keys[0] та new_key є на диску, keys[1] — видалено
        assert (tmp_path / keys[0]).is_file()
        assert (tmp_path / new_key).is_file()
        assert not (tmp_path / keys[1]).is_file()

        # 4. Перевірка публічного отримання
        get_res = client.get(f"/api/v1/listings/{listing_id}")
        assert get_res.status_code == 200
        images = get_res.json()["images"]
        assert len(images) == 2
        assert images[0]["image_url"] == f"/uploads/{keys[0]}"
        assert images[1]["image_url"] == f"/uploads/{new_key}"

    finally:
        app.dependency_overrides.pop(get_image_storage, None)
        app.dependency_overrides.pop(get_listing_service, None)
