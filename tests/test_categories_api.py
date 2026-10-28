"""Інтеграційні API-тести для категорій оголошень (FR-012, SEC-002).

Тести як специфікація: визначають HTTP-контракт GET /api/v1/categories
та GET /api/v1/categories/{id}.
Тест-кейси: TP-016, TP-017.
"""

from uuid import uuid4
from fastapi.testclient import TestClient

from src.domain.listings import SEED_CATEGORY_ID

URL = "/api/v1/categories"


def test_list_categories_returns_200_and_active_categories(
    client: TestClient,
) -> None:
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
    # Act
    response = client.get(f"{URL}/{SEED_CATEGORY_ID}")

    # Assert
    assert response.status_code == 200
    category = response.json()
    assert category["id"] == str(SEED_CATEGORY_ID)
    assert category["is_active"] is True


def test_get_category_by_id_not_found(client: TestClient) -> None:
    non_existent = uuid4()
    response = client.get(f"{URL}/{non_existent}")
    assert response.status_code == 404
    assert "не знайдено" in response.json()["detail"].lower()


def test_get_category_by_invalid_uuid_returns_422(client: TestClient) -> None:
    response = client.get(f"{URL}/invalid-uuid-format")
    assert response.status_code == 422
