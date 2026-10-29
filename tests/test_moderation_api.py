"""HTTP-тести адміністративної модерації оголошень (FR-011, SEC-001)."""

from uuid import uuid4

from fastapi.testclient import TestClient

from src.domain.listings import (
    ListingStatus,
    SEED_LISTING_ID,
    WITHDRAWN_LISTING_ID,
)
from src.domain.moderation import MODERATION_REASON_MAX_LENGTH
from src.domain.users import UserRole

REASON = "Продаж заборонених товарів"
SEED_CONTACT = "@student_ukma"


def withdraw_url(listing_id: object) -> str:
    return f"/api/v1/admin/listings/{listing_id}/withdraw"


def test_admin_withdraws_listing(
    client: TestClient, login_as, listing_repository, moderation_actions
) -> None:
    """[TP-021] [FR-011]
    ADMIN знімає оголошення: 201, WITHDRAWN, зникає з каталогу, причина в аудиті.
    """
    # Arrange
    admin = login_as(role=UserRole.ADMIN)
    # Act
    response = client.post(withdraw_url(SEED_LISTING_ID), json={"reason": REASON})
    # Assert
    assert response.status_code == 201
    body = response.json()
    assert body["listing_id"] == str(SEED_LISTING_ID)
    assert body["moderator_id"] == str(admin.user_id)
    assert body["action_type"] == "WITHDRAW_LISTING"
    assert body["reason"] == REASON
    assert listing_repository.get(SEED_LISTING_ID).status == ListingStatus.WITHDRAWN
    [action] = moderation_actions.list_by_listing(SEED_LISTING_ID)
    assert action.moderator_id == admin.user_id
    assert action.reason == REASON
    catalog_ids = {item["id"] for item in client.get("/api/v1/listings").json()}
    assert str(SEED_LISTING_ID) not in catalog_ids
    assert client.get(f"/api/v1/listings/{SEED_LISTING_ID}").status_code == 404


def test_withdrawn_by_admin_disappears_from_buyer_favorites(
    client: TestClient, login_as
) -> None:
    """[TP-021] [FR-011] [FR-009] Після модерації оголошення зникає з обраного."""
    login_as()
    client.post(f"/api/v1/favorites/{SEED_LISTING_ID}")
    buyer_cookie = client.cookies.get("baraholka_session")

    login_as(role=UserRole.ADMIN)
    assert (
        client.post(withdraw_url(SEED_LISTING_ID), json={"reason": REASON}).status_code
        == 201
    )

    client.cookies.set("baraholka_session", buyer_cookie)
    assert client.get("/api/v1/favorites").json() == []


def test_moderation_without_session_is_401(client: TestClient) -> None:
    """[TP-021] [FR-011] [SEC-001] Без серверної сесії — 401."""
    response = client.post(withdraw_url(SEED_LISTING_ID), json={"reason": REASON})
    assert response.status_code == 401


def test_regular_user_is_403(client: TestClient, login_as, listing_repository) -> None:
    """[TP-021] [FR-011] [SEC-001] Користувач без ролі ADMIN отримує 403."""
    login_as()
    response = client.post(withdraw_url(SEED_LISTING_ID), json={"reason": REASON})
    assert response.status_code == 403
    assert listing_repository.get(SEED_LISTING_ID).status == ListingStatus.ACTIVE


def test_spoofed_admin_fields_do_not_grant_rights(
    client: TestClient, login_as, listing_repository, moderation_actions
) -> None:
    """[TP-021] [FR-011] [SEC-001]
    Поле role=ADMIN, чужий moderator_id чи заголовки не надають прав ADMIN.
    """
    login_as()
    response = client.post(
        withdraw_url(SEED_LISTING_ID),
        json={"reason": REASON, "role": "ADMIN", "moderator_id": str(uuid4())},
        headers={"X-Actor-Id": str(uuid4()), "X-Actor-Role": "ADMIN"},
    )
    assert response.status_code == 403
    assert listing_repository.get(SEED_LISTING_ID).status == ListingStatus.ACTIVE
    assert moderation_actions.list_by_listing(SEED_LISTING_ID) == []


def test_blocked_admin_is_403(client: TestClient, login_as) -> None:
    """[TP-021] [FR-011] [SEC-001] Заблокований адміністратор не модерує."""
    login_as(role=UserRole.ADMIN, is_blocked=True)
    response = client.post(withdraw_url(SEED_LISTING_ID), json={"reason": REASON})
    assert response.status_code == 403


def test_invalid_reason_is_422(
    client: TestClient, login_as, moderation_actions
) -> None:
    """[TP-021] [FR-011]
    Відсутня, порожня, пробільна або завелика причина повертає 422.
    """
    login_as(role=UserRole.ADMIN)
    for body in (
        {},
        {"reason": ""},
        {"reason": "     "},
        {"reason": "x" * (MODERATION_REASON_MAX_LENGTH + 1)},
    ):
        response = client.post(withdraw_url(SEED_LISTING_ID), json=body)
        assert response.status_code == 422, body
    assert moderation_actions.list_by_listing(SEED_LISTING_ID) == []


def test_unknown_listing_is_404(client: TestClient, login_as) -> None:
    """[TP-021] [FR-011] Неіснуюче оголошення повертає 404."""
    login_as(role=UserRole.ADMIN)
    response = client.post(withdraw_url(uuid4()), json={"reason": REASON})
    assert response.status_code == 404


def test_already_withdrawn_listing_is_404(client: TestClient, login_as) -> None:
    """[TP-021] [FR-011] Уже зняте оголошення повертає 404."""
    login_as(role=UserRole.ADMIN)
    response = client.post(withdraw_url(WITHDRAWN_LISTING_ID), json={"reason": REASON})
    assert response.status_code == 404


def test_invalid_listing_id_is_422(client: TestClient, login_as) -> None:
    """[TP-021] [FR-011] Некоректний UUID оголошення повертає 422."""
    login_as(role=UserRole.ADMIN)
    response = client.post(withdraw_url("not-a-uuid"), json={"reason": REASON})
    assert response.status_code == 422


def test_error_bodies_do_not_leak_contact(client: TestClient, login_as) -> None:
    """[TP-021] [FR-011] [SEC-002] Відповіді 401/403/404 не містять контакту."""
    responses = [client.post(withdraw_url(SEED_LISTING_ID), json={"reason": REASON})]
    login_as()
    responses.append(
        client.post(withdraw_url(SEED_LISTING_ID), json={"reason": REASON})
    )
    login_as(role=UserRole.ADMIN)
    responses.append(client.post(withdraw_url(uuid4()), json={"reason": REASON}))
    assert [r.status_code for r in responses] == [401, 403, 404]
    for response in responses:
        assert SEED_CONTACT not in response.text
