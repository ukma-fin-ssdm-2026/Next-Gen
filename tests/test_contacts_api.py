"""HTTP-тести доступу до контакту продавця (FR-010, SEC-002, SEC-001)."""

from uuid import uuid4

from fastapi.testclient import TestClient

from src.domain.listings import SEED_LISTING_ID, SEED_OWNER_ID, WITHDRAWN_LISTING_ID

SEED_CONTACT = "@student_ukma"
WITHDRAWN_CONTACT = "@hidden_contact"


def contact_url(listing_id: object) -> str:
    return f"/api/v1/listings/{listing_id}/contact"


def test_authenticated_buyer_gets_contact(client: TestClient, login_as) -> None:
    """[TP-019] [FR-010] [SEC-002]
    Автентифікований покупець отримує контакт активного оголошення (200).
    """
    login_as()
    response = client.get(contact_url(SEED_LISTING_ID))
    assert response.status_code == 200
    assert response.json() == {
        "listing_id": str(SEED_LISTING_ID),
        "contact": SEED_CONTACT,
    }
    assert response.headers["cache-control"] == "no-store"


def test_anonymous_request_is_401_without_contact(client: TestClient) -> None:
    """[TP-019] [FR-010] [SEC-002] Анонімний запит отримує 401 без контакту."""
    response = client.get(contact_url(SEED_LISTING_ID))
    assert response.status_code == 401
    assert "contact" not in response.json()
    assert SEED_CONTACT not in response.text


def test_legacy_actor_header_does_not_unlock_contact(client: TestClient) -> None:
    """[TP-019] [FR-010] [SEC-002]
    Заголовок X-Actor-Id без серверної сесії не відкриває контакт.
    """
    response = client.get(
        contact_url(SEED_LISTING_ID), headers={"X-Actor-Id": str(SEED_OWNER_ID)}
    )
    assert response.status_code == 401
    assert SEED_CONTACT not in response.text


def test_blocked_user_cannot_get_contact(client: TestClient, login_as) -> None:
    """[TP-019] [FR-010] [SEC-001] Заблокований користувач отримує 403 без контакту."""
    login_as(is_blocked=True)
    response = client.get(contact_url(SEED_LISTING_ID))
    assert response.status_code == 403
    assert SEED_CONTACT not in response.text


def test_withdrawn_listing_contact_is_404(client: TestClient, login_as) -> None:
    """[TP-019] [FR-010] [SEC-002]
    Для знятого оголошення 404, тіло помилки не містить контакту.
    """
    login_as()
    response = client.get(contact_url(WITHDRAWN_LISTING_ID))
    assert response.status_code == 404
    assert WITHDRAWN_CONTACT not in response.text


def test_unknown_listing_contact_is_404(client: TestClient, login_as) -> None:
    """[TP-019] [FR-010] Неіснуюче оголошення повертає 404."""
    login_as()
    assert client.get(contact_url(uuid4())).status_code == 404


def test_invalid_listing_id_is_422(client: TestClient, login_as) -> None:
    """[TP-019] [FR-010] Некоректний UUID оголошення повертає 422."""
    login_as()
    assert client.get(contact_url("not-a-uuid")).status_code == 422


def test_contact_disappears_after_owner_withdraws(client: TestClient, login_as) -> None:
    """[TP-019] [FR-010] [SEC-002]
    Після зняття оголошення власником контакт більше не видається (404).
    """
    login_as()
    assert client.get(contact_url(SEED_LISTING_ID)).status_code == 200
    owner = {"X-Actor-Id": str(SEED_OWNER_ID)}
    client.delete(f"/api/v1/listings/{SEED_LISTING_ID}", headers=owner)
    response = client.get(contact_url(SEED_LISTING_ID))
    assert response.status_code == 404
    assert SEED_CONTACT not in response.text


def test_public_views_never_include_contact_even_with_session(
    client: TestClient, login_as
) -> None:
    """[TP-N01] [SEC-002]
    Навіть із сесією каталог, деталі й обране не містять контакту продавця.
    """
    login_as()
    client.post(f"/api/v1/favorites/{SEED_LISTING_ID}")
    for url in (
        "/api/v1/listings",
        f"/api/v1/listings/{SEED_LISTING_ID}",
        "/api/v1/favorites",
    ):
        response = client.get(url)
        assert response.status_code == 200
        assert SEED_CONTACT not in response.text, url
