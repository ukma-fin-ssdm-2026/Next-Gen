"""HTTP-тести обраного (FR-009) і контролю доступу (TM-02, SEC-002)."""

from uuid import uuid4

from fastapi.testclient import TestClient

from src.domain.listings import SEED_LISTING_ID, SEED_OWNER_ID, WITHDRAWN_LISTING_ID

BUYER = {"X-Actor-Id": str(uuid4())}
URL = "/api/v1/favorites"


def test_add_favorite_returns_201(client: TestClient) -> None:
    response = client.post(f"{URL}/{SEED_LISTING_ID}", headers=BUYER)
    assert response.status_code == 201
    assert response.json()["listing_id"] == str(SEED_LISTING_ID)


def test_list_favorites_returns_public_listings(client: TestClient) -> None:
    # Arrange
    client.post(f"{URL}/{SEED_LISTING_ID}", headers=BUYER)
    # Act
    response = client.get(URL, headers=BUYER)
    # Assert: оголошення є, а контакту продавця немає (SEC-002)
    assert response.status_code == 200
    items = response.json()
    assert [item["id"] for item in items] == [str(SEED_LISTING_ID)]
    assert "contact" not in items[0]


def test_add_twice_keeps_single_entry(client: TestClient) -> None:
    client.post(f"{URL}/{SEED_LISTING_ID}", headers=BUYER)
    second = client.post(f"{URL}/{SEED_LISTING_ID}", headers=BUYER)
    assert second.status_code == 201
    assert len(client.get(URL, headers=BUYER).json()) == 1


def test_favorites_require_actor(client: TestClient) -> None:
    assert client.get(URL).status_code == 401
    assert client.post(f"{URL}/{SEED_LISTING_ID}").status_code == 401
    assert client.delete(f"{URL}/{SEED_LISTING_ID}").status_code == 401


def test_add_withdrawn_or_unknown_listing_is_404(client: TestClient) -> None:
    withdrawn = client.post(f"{URL}/{WITHDRAWN_LISTING_ID}", headers=BUYER)
    unknown = client.post(f"{URL}/{uuid4()}", headers=BUYER)
    assert withdrawn.status_code == 404
    assert unknown.status_code == 404


def test_invalid_listing_id_is_422(client: TestClient) -> None:
    assert client.post(f"{URL}/not-a-uuid", headers=BUYER).status_code == 422


def test_favorites_are_private_per_user(client: TestClient) -> None:
    client.post(f"{URL}/{SEED_LISTING_ID}", headers=BUYER)
    other = {"X-Actor-Id": str(uuid4())}
    assert client.get(URL, headers=other).json() == []


def test_remove_favorite_returns_204(client: TestClient) -> None:
    client.post(f"{URL}/{SEED_LISTING_ID}", headers=BUYER)
    response = client.delete(f"{URL}/{SEED_LISTING_ID}", headers=BUYER)
    assert response.status_code == 204
    assert client.get(URL, headers=BUYER).json() == []


def test_remove_missing_favorite_is_404(client: TestClient) -> None:
    response = client.delete(f"{URL}/{SEED_LISTING_ID}", headers=BUYER)
    assert response.status_code == 404


def test_withdrawn_listing_disappears_from_favorites(client: TestClient) -> None:
    # Arrange: покупець зберіг оголошення
    client.post(f"{URL}/{SEED_LISTING_ID}", headers=BUYER)
    # Act: власник знімає його з публікації
    owner = {"X-Actor-Id": str(SEED_OWNER_ID)}
    withdraw = client.delete(f"/api/v1/listings/{SEED_LISTING_ID}", headers=owner)
    # Assert: в обраному покупця його більше немає (FR-009)
    assert withdraw.status_code == 204
    assert client.get(URL, headers=BUYER).json() == []
