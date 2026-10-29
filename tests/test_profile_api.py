"""HTTP-тести профілю користувача (FR-014, US-009, SEC-002)."""

from uuid import uuid4

from fastapi.testclient import TestClient

from tests.conftest import make_dummy_jpeg

ME = "/api/v1/auth/me"
AVATAR = "/api/v1/auth/me/avatar"


def test_patch_me_updates_name_and_contact(client: TestClient, login_as) -> None:
    """[TP-025] [US-009] [FR-014] PATCH /auth/me змінює ім'я та контакти."""
    login_as()
    response = client.patch(ME, json={"display_name": "Іван", "contact": "@ivan"})
    assert response.status_code == 200
    assert response.json()["display_name"] == "Іван"
    assert client.get(ME).json()["contact"] == "@ivan"
    cleared = client.patch(ME, json={"contact": None})
    assert cleared.json()["contact"] is None
    assert cleared.json()["display_name"] == "Іван"


def test_patch_me_validation(client: TestClient, login_as) -> None:
    """[TP-025] [FR-014] Порожнє ім'я, довгі контакти та null-ім'я — 422."""
    login_as()
    assert client.patch(ME, json={"display_name": ""}).status_code == 422
    assert client.patch(ME, json={"contact": "x" * 301}).status_code == 422
    assert client.patch(ME, json={"display_name": None}).status_code == 422
    assert client.patch(ME, json={"display_name": "   "}).status_code == 422


def test_profile_requires_session_and_not_blocked(client: TestClient, login_as) -> None:
    """[TP-025] [FR-014] [SEC-001] Без сесії — 401, заблокований — 403."""
    assert client.patch(ME, json={"contact": "x"}).status_code == 401
    assert (
        client.put(AVATAR, files={"file": ("a.jpg", make_dummy_jpeg())}).status_code
        == 401
    )
    assert client.delete(AVATAR).status_code == 401
    login_as(is_blocked=True)
    assert client.patch(ME, json={"contact": "x"}).status_code == 403


def test_avatar_upload_and_delete(client: TestClient, login_as) -> None:
    """[TP-025] [FR-014] [TM-03] PUT/DELETE аватарки; файл віддається через /uploads."""
    login_as()
    response = client.put(
        AVATAR, files={"file": ("a.jpg", make_dummy_jpeg(), "image/jpeg")}
    )
    assert response.status_code == 200
    url = response.json()["avatar_url"]
    assert url.startswith("/uploads/") and url.endswith(".webp")
    assert client.get(ME).json()["avatar_url"] == url
    assert client.delete(AVATAR).json()["avatar_url"] is None


def test_avatar_invalid_file_is_422(client: TestClient, login_as) -> None:
    """[TP-025] [FR-014] [TM-03] Невалідний або завеликий файл аватарки — 422."""
    login_as()
    bad = client.put(AVATAR, files={"file": ("a.jpg", b"nope", "image/jpeg")})
    assert bad.status_code == 422
    huge = client.put(AVATAR, files={"file": ("a.jpg", b"0" * (10 * 1024 * 1024 + 1))})
    assert huge.status_code == 422


def test_public_profile_hides_private_fields(client: TestClient, login_as) -> None:
    """[TP-025] [FR-014] [SEC-002] Публічний профіль: лише ім'я й аватарка."""
    owner = login_as()
    client.patch(ME, json={"display_name": "Продавець", "contact": "@secret"})
    login_as()
    response = client.get(f"/api/v1/users/{owner.user_id}")
    assert response.status_code == 200
    assert response.json() == {
        "user_id": str(owner.user_id),
        "display_name": "Продавець",
        "avatar_url": None,
    }
    assert "@secret" not in response.text and owner.email not in response.text


def test_public_profile_errors(client: TestClient, login_as) -> None:
    """[TP-025] [FR-014] Профіль без сесії — 401, невідомий — 404, поганий id — 422."""
    assert client.get(f"/api/v1/users/{uuid4()}").status_code == 401
    login_as()
    assert client.get(f"/api/v1/users/{uuid4()}").status_code == 404
    assert client.get("/api/v1/users/not-a-uuid").status_code == 422
