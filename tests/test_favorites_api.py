"""HTTP-тести обраного (FR-009) і контролю доступу (SEC-001, SEC-002).

Покупець ідентифікується лише серверною сесією (cookie `baraholka_session`),
тому кожен тест входить через фікстуру `login_as`, а не через `X-Actor-Id`.
"""

from uuid import uuid4

from fastapi.testclient import TestClient

from src.api.deps import SESSION_COOKIE_NAME
from src.domain.listings import SEED_LISTING_ID, SEED_OWNER_ID, WITHDRAWN_LISTING_ID

URL = "/api/v1/favorites"


def test_add_favorite_returns_201(client: TestClient, login_as) -> None:
    """[TP-012] [FR-009] POST /favorites додає оголошення та повертає 201 Created."""
    login_as()
    response = client.post(f"{URL}/{SEED_LISTING_ID}")
    assert response.status_code == 201
    assert response.json()["listing_id"] == str(SEED_LISTING_ID)


def test_list_favorites_returns_public_listings(client: TestClient, login_as) -> None:
    """[TP-013] [FR-009] [SEC-002]
    Публічний перегляд обраного без розкриття контактів продавця.
    """
    # Arrange
    login_as()
    client.post(f"{URL}/{SEED_LISTING_ID}")
    # Act
    response = client.get(URL)
    # Assert: оголошення є, а контакту продавця немає (SEC-002)
    assert response.status_code == 200
    items = response.json()
    assert [item["id"] for item in items] == [str(SEED_LISTING_ID)]
    assert "contact" not in items[0]


def test_add_twice_keeps_single_entry(client: TestClient, login_as) -> None:
    """[TP-012] [FR-009] Повторний POST зберігає єдиний запис в обраному."""
    login_as()
    client.post(f"{URL}/{SEED_LISTING_ID}")
    second = client.post(f"{URL}/{SEED_LISTING_ID}")
    assert second.status_code == 201
    assert len(client.get(URL).json()) == 1


def test_favorites_require_session(client: TestClient) -> None:
    """[TP-012] [FR-009] [SEC-001] Доступ до обраного без сесії повертає 401."""
    assert client.get(URL).status_code == 401
    assert client.post(f"{URL}/{SEED_LISTING_ID}").status_code == 401
    assert client.delete(f"{URL}/{SEED_LISTING_ID}").status_code == 401


def test_favorites_ignore_legacy_actor_header(client: TestClient) -> None:
    """[TP-012] [FR-009] [SEC-001]
    Заголовок X-Actor-Id без сесії більше не ідентифікує користувача (401).
    """
    spoofed = {"X-Actor-Id": str(uuid4())}
    assert client.get(URL, headers=spoofed).status_code == 401
    assert client.post(f"{URL}/{SEED_LISTING_ID}", headers=spoofed).status_code == 401


def test_unknown_session_cookie_is_401(client: TestClient, login_as) -> None:
    """[TP-012] [FR-009] [SEC-001] Невідома або підроблена cookie сесії дає 401."""
    login_as()
    client.cookies.set(SESSION_COOKIE_NAME, "forged-session-token")
    assert client.get(URL).status_code == 401


def test_blocked_user_cannot_use_favorites(client: TestClient, login_as) -> None:
    """[TP-012] [FR-009] [SEC-001]
    Заблокований користувач не користується обраним навіть із чинною сесією.
    """
    login_as(is_blocked=True)
    response = client.get(URL)
    assert response.status_code == 403
    assert "contact" not in response.text


def test_add_withdrawn_or_unknown_listing_is_404(client: TestClient, login_as) -> None:
    """[TP-012] [FR-009] Додавання неіснуючого чи знятого оголошення повертає 404."""
    login_as()
    withdrawn = client.post(f"{URL}/{WITHDRAWN_LISTING_ID}")
    unknown = client.post(f"{URL}/{uuid4()}")
    assert withdrawn.status_code == 404
    assert unknown.status_code == 404


def test_invalid_listing_id_is_422(client: TestClient, login_as) -> None:
    """[TP-012] [FR-009] Некоректний формат UUID оголошення повертає 422."""
    login_as()
    assert client.post(f"{URL}/not-a-uuid").status_code == 422


def test_favorites_are_private_per_user(client: TestClient, login_as) -> None:
    """[TP-013] [FR-009] [SEC-001]
    Приватність обраного: інший користувач не бачить чужого списку.
    """
    login_as()
    client.post(f"{URL}/{SEED_LISTING_ID}")
    login_as()
    assert client.get(URL).json() == []


def test_client_supplied_identity_does_not_open_foreign_list(
    client: TestClient, login_as
) -> None:
    """[TP-013] [FR-009] [SEC-001]
    Підміна ідентифікатора в заголовку чи query не дає доступу до чужого обраного.
    """
    # Arrange: власник списку додав оголошення
    owner = login_as()
    client.post(f"{URL}/{SEED_LISTING_ID}")
    # Act: інший користувач підставляє чужий user_id усіма доступними способами
    login_as()
    response = client.get(
        URL,
        params={"user_id": str(owner.user_id)},
        headers={"X-Actor-Id": str(owner.user_id)},
    )
    # Assert: бачить лише власний (порожній) список
    assert response.status_code == 200
    assert response.json() == []


def test_remove_favorite_returns_204(client: TestClient, login_as) -> None:
    """[TP-014] [FR-009] Видалення оголошення з обраного повертає HTTP 204."""
    login_as()
    client.post(f"{URL}/{SEED_LISTING_ID}")
    response = client.delete(f"{URL}/{SEED_LISTING_ID}")
    assert response.status_code == 204
    assert client.get(URL).json() == []


def test_remove_missing_favorite_is_404(client: TestClient, login_as) -> None:
    """[TP-014] [FR-009] Спроба видалити відсутнє в обраному оголошення повертає 404."""
    login_as()
    response = client.delete(f"{URL}/{SEED_LISTING_ID}")
    assert response.status_code == 404


def test_cannot_remove_foreign_favorite(client: TestClient, login_as) -> None:
    """[TP-014] [FR-009] [SEC-001]
    DELETE прибирає запис лише з власного обраного; чужий запис лишається.
    """
    login_as()
    client.post(f"{URL}/{SEED_LISTING_ID}")
    owner_cookie = client.cookies.get(SESSION_COOKIE_NAME)

    login_as()
    assert client.delete(f"{URL}/{SEED_LISTING_ID}").status_code == 404

    client.cookies.set(SESSION_COOKIE_NAME, owner_cookie)
    assert [item["id"] for item in client.get(URL).json()] == [str(SEED_LISTING_ID)]


def test_withdrawn_listing_disappears_from_favorites(
    client: TestClient, login_as
) -> None:
    """[TP-014] [FR-009] Зняття оголошення з публікації прибирає його з обраного."""
    # Arrange: покупець зберіг оголошення
    login_as()
    client.post(f"{URL}/{SEED_LISTING_ID}")
    # Act: власник знімає його з публікації (блок оголошень ще на X-Actor-Id)
    owner = {"X-Actor-Id": str(SEED_OWNER_ID)}
    withdraw = client.delete(f"/api/v1/listings/{SEED_LISTING_ID}", headers=owner)
    # Assert: в обраному покупця його більше немає (FR-009)
    assert withdraw.status_code == 204
    assert client.get(URL).json() == []
