"""HTTP-тести блокування користувачів (FR-013, SEC-001)."""

from uuid import uuid4

from fastapi.testclient import TestClient

from src.domain.users import UserRole

REASON = "Систематичні порушення правил"


def block_url(user_id: object) -> str:
    return f"/api/v1/admin/users/{user_id}/block"


def unblock_url(user_id: object) -> str:
    return f"/api/v1/admin/users/{user_id}/unblock"


def test_admin_blocks_and_unblocks_user(
    client: TestClient, login_as, moderation_actions
) -> None:
    """[TP-027] [FR-013] ADMIN блокує й розблоковує: 201, аудит, без listing_id."""
    target = login_as()
    admin = login_as(role=UserRole.ADMIN)
    blocked = client.post(block_url(target.user_id), json={"reason": REASON})
    assert blocked.status_code == 201
    body = blocked.json()
    assert body["action_type"] == "BLOCK_USER"
    assert body["target_user_id"] == str(target.user_id)
    assert body["moderator_id"] == str(admin.user_id)
    assert body["listing_id"] is None
    unblocked = client.post(unblock_url(target.user_id), json={"reason": REASON})
    assert unblocked.status_code == 201
    assert unblocked.json()["action_type"] == "UNBLOCK_USER"
    assert len(moderation_actions.list_by_user(target.user_id)) == 2


def test_blocked_user_loses_session_and_actions(client: TestClient, login_as) -> None:
    """[TP-027] [FR-013] [SEC-001]
    Після блокування чинна сесія недійсна, мутуючі дії недоступні, після
    розблокування користувач знову має працювати з новою сесією.
    """
    target = login_as()
    target_cookie = client.cookies.get("baraholka_session")
    assert client.get("/api/v1/auth/me").status_code == 200
    login_as(role=UserRole.ADMIN)
    assert (
        client.post(block_url(target.user_id), json={"reason": REASON}).status_code
        == 201
    )
    client.cookies.set("baraholka_session", target_cookie)
    assert client.get("/api/v1/auth/me").status_code == 401
    assert client.post("/api/v1/favorites/" + str(uuid4())).status_code == 401


def test_block_requires_admin_session(client: TestClient, login_as) -> None:
    """[TP-027] [FR-013] [SEC-001]
    Без сесії 401; USER, заблокований адмін, підроблені заголовки — 403.
    """
    target = login_as()
    client.cookies.clear()
    assert (
        client.post(block_url(target.user_id), json={"reason": REASON}).status_code
        == 401
    )
    login_as()
    forged = client.post(
        block_url(target.user_id),
        json={"reason": REASON, "role": "ADMIN"},
        headers={"X-Actor-Role": "ADMIN"},
    )
    assert forged.status_code == 403
    login_as(role=UserRole.ADMIN, is_blocked=True)
    assert (
        client.post(block_url(target.user_id), json={"reason": REASON}).status_code
        == 403
    )
    # Сесію заблокованого адміністратора відкликано після першого запиту.
    login_as(role=UserRole.ADMIN, is_blocked=True)
    assert (
        client.post(unblock_url(target.user_id), json={"reason": REASON}).status_code
        == 403
    )


def test_block_error_codes(client: TestClient, login_as) -> None:
    """[TP-027] [FR-013] 404 невідомий, 409 сам/адмін/повтор, 422 причина й UUID."""
    admin = login_as(role=UserRole.ADMIN)
    target = login_as()
    login_as(role=UserRole.ADMIN, user_id=admin.user_id)
    assert client.post(block_url(uuid4()), json={"reason": REASON}).status_code == 404
    assert (
        client.post(block_url(admin.user_id), json={"reason": REASON}).status_code
        == 409
    )
    assert (
        client.post(unblock_url(target.user_id), json={"reason": REASON}).status_code
        == 409
    )
    assert (
        client.post(block_url(target.user_id), json={"reason": REASON}).status_code
        == 201
    )
    assert (
        client.post(block_url(target.user_id), json={"reason": REASON}).status_code
        == 409
    )
    assert (
        client.post(block_url(target.user_id), json={"reason": "abc"}).status_code
        == 422
    )
    assert client.post(block_url(target.user_id), json={}).status_code == 422
    assert (
        client.post(block_url("not-a-uuid"), json={"reason": REASON}).status_code == 422
    )
