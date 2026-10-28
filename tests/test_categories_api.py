"""Інтеграційні API-тести для категорій оголошень (FR-012, SEC-002).

Тести як специфікація: визначають HTTP-контракт GET /api/v1/categories,
GET /api/v1/categories/{id}, а також адміністративних операцій POST та PATCH.
Тест-кейси: TP-016, TP-017.
"""

from uuid import uuid4
from fastapi.testclient import TestClient

from src.domain.listings import SEED_CATEGORY_ID

URL = "/api/v1/categories"
ADMIN_HEADER = {"X-Actor-Role": "ADMIN"}
STUDENT_HEADER = {"X-Actor-Role": "STUDENT"}


def test_list_categories_returns_200_and_active_categories(
    client: TestClient,
) -> None:
    """[TP-016] [FR-012]
    Публічний GET /categories повертає список активних категорій.
    """
    # Act
    response = client.get(URL)

    # Assert
    assert response.status_code == 200
    categories = response.json()
    assert isinstance(categories, list)
    assert len(categories) >= 4

    ids = [cat["id"] for cat in categories]
    assert str(SEED_CATEGORY_ID) in ids

    # Перевірка структури відповіді
    first = categories[0]
    assert "id" in first
    assert "name" in first
    assert "slug" in first
    assert "description" in first
    assert "is_active" in first
    assert first["is_active"] is True


def test_get_category_by_id_success(client: TestClient) -> None:
    """[TP-017] [FR-012] Отримання конкретної категорії за ID (HTTP 200)."""
    # Act
    response = client.get(f"{URL}/{SEED_CATEGORY_ID}")

    # Assert
    assert response.status_code == 200
    category = response.json()
    assert category["id"] == str(SEED_CATEGORY_ID)
    assert category["is_active"] is True


def test_get_category_by_id_not_found(client: TestClient) -> None:
    """[TP-017] [FR-012] Запит неіснуючої категорії повертає HTTP 404."""
    non_existent = uuid4()
    response = client.get(f"{URL}/{non_existent}")
    assert response.status_code == 404
    assert "не знайдено" in response.json()["detail"].lower()


def test_get_category_by_invalid_uuid_returns_422(client: TestClient) -> None:
    """[TP-017] [FR-012] Некоректний формат UUID повертає HTTP 422."""
    response = client.get(f"{URL}/invalid-uuid-format")
    assert response.status_code == 422


def test_admin_create_category_success(client: TestClient) -> None:
    """[TP-017] [FR-012] Адміністратор може створити нову категорію (HTTP 201)."""
    payload = {
        "name": "Настільні ігри НаУКМА",
        "slug": f"board-games-{uuid4().hex[:6]}",
        "description": "Клуб настілок та обмін іграми",
    }
    response = client.post(URL, json=payload, headers=ADMIN_HEADER)
    assert response.status_code == 201
    created = response.json()
    assert created["name"] == payload["name"]
    assert created["slug"] == payload["slug"]
    assert created["is_active"] is True


def test_non_admin_cannot_create_category(client: TestClient) -> None:
    """[TP-017] [FR-012]
    Не-адміністратор отримує HTTP 403 Forbidden при спробі створення категорії.
    """
    payload = {
        "name": "Недозволена категорія",
        "slug": "unauthorized-cat",
    }
    # Без заголовка ролі
    res_no_role = client.post(URL, json=payload)
    assert res_no_role.status_code == 403

    # З роллю студента
    res_student = client.post(URL, json=payload, headers=STUDENT_HEADER)
    assert res_student.status_code == 403


def test_create_category_duplicate_slug_returns_409(client: TestClient) -> None:
    """[TP-017] [FR-012]
    Спроба створити категорію з існуючим slug повертає HTTP 409 Conflict.
    """
    payload = {
        "name": "Дублюючі підручники",
        "slug": "textbooks",  # вже є в seed
    }
    response = client.post(URL, json=payload, headers=ADMIN_HEADER)
    assert response.status_code == 409
    assert "вже існує" in response.json()["detail"].lower()


def test_admin_update_category_and_deactivate(client: TestClient) -> None:
    """[TP-017] [FR-012]
    Адміністратор може оновити та деактивувати категорію (HTTP 200).
    """
    # Створюємо унікальну категорію для оновлення
    create_payload = {
        "name": "Тимчасова категорія",
        "slug": f"temp-cat-{uuid4().hex[:6]}",
        "description": "Опис до оновлення",
    }
    created = client.post(URL, json=create_payload, headers=ADMIN_HEADER).json()
    cat_id = created["id"]

    # Оновлюємо та деактивуємо
    update_payload = {
        "name": "Оновлена назва",
        "is_active": False,
    }
    response = client.patch(
        f"{URL}/{cat_id}", json=update_payload, headers=ADMIN_HEADER
    )
    assert response.status_code == 200
    updated = response.json()
    assert updated["name"] == "Оновлена назва"
    assert updated["is_active"] is False

    # Перевіряємо, що після деактивації категорія зникла з публічного списку
    public_list = client.get(URL).json()
    assert cat_id not in [cat["id"] for cat in public_list]


def test_non_admin_cannot_update_category(client: TestClient) -> None:
    """[TP-017] [FR-012]
    Не-адміністратор отримує HTTP 403 при спробі оновлення категорії.
    """
    response = client.patch(
        f"{URL}/{SEED_CATEGORY_ID}",
        json={"name": "Хакерське перейменування"},
        headers=STUDENT_HEADER,
    )
    assert response.status_code == 403
