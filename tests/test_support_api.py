"""HTTP-тести скарг, звернень, журналів і заблокованих (FR-013, FR-016..018)."""

from uuid import uuid4

from fastapi.testclient import TestClient

from src.domain.users import UserRole

BLOCK_REASON = "Систематичні порушення правил"


def _create_listing(client: TestClient, payload: dict) -> str:
    response = client.post("/api/v1/listings", json=payload)
    assert response.status_code == 201, response.text
    return response.json()["id"]


def _complain(client: TestClient, listing_id: str, **body):
    body.setdefault("reason", "SPAM")
    return client.post(f"/api/v1/listings/{listing_id}/complaints", json=body)


# --- Скарги (FR-016) -------------------------------------------------------


def test_user_complains_and_admin_sees_complaint(
    client: TestClient, login_as, listing_payload
) -> None:
    """[TP-031] [FR-016] Користувач скаржиться, адмін бачить скаргу."""
    login_as()
    listing_id = _create_listing(client, listing_payload)
    reporter = login_as()
    created = _complain(
        client, listing_id, reason="FRAUD", details="Підозра на шахрайство"
    )
    assert created.status_code == 201
    assert created.json()["status"] == "OPEN"
    login_as(role=UserRole.ADMIN)
    listed = client.get("/api/v1/admin/complaints")
    assert listed.status_code == 200
    item = listed.json()[0]
    assert item["listing_id"] == listing_id
    assert item["listing_title"] == listing_payload["title"]
    assert item["reporter_email"] == reporter.email
    assert item["reason"] == "FRAUD"
    assert client.get("/api/v1/admin/complaints?status=RESOLVED").json() == []


def test_complaint_validation_and_rules(
    client: TestClient, login_as, listing_payload
) -> None:
    """[TP-031] [FR-016] Власне оголошення, дубль, OTHER без опису, невідоме."""
    login_as()
    listing_id = _create_listing(client, listing_payload)
    own = _complain(client, listing_id)
    assert own.status_code == 422
    login_as()
    assert _complain(client, listing_id, reason="OTHER").status_code == 422
    assert _complain(client, str(uuid4())).status_code == 404
    assert _complain(client, listing_id).status_code == 201
    assert _complain(client, listing_id).status_code == 409
    assert _complain(client, listing_id, reason="BOGUS").status_code == 422


def test_complaint_requires_session(client: TestClient, listing_payload) -> None:
    """[TP-031] [FR-016] [SEC-001] Скарга без сесії — 401."""
    assert _complain(client, str(uuid4())).status_code == 401
    assert client.get("/api/v1/admin/complaints").status_code == 401


def test_complaints_admin_only_and_resolve(
    client: TestClient, login_as, listing_payload
) -> None:
    """[TP-031] [FR-016] [SEC-001] USER не бачить скарги; ADMIN розглядає один раз."""
    login_as()
    listing_id = _create_listing(client, listing_payload)
    login_as()
    complaint_id = _complain(client, listing_id).json()["id"]
    resolve_url = f"/api/v1/admin/complaints/{complaint_id}/resolve"
    assert client.get("/api/v1/admin/complaints").status_code == 403
    assert client.post(resolve_url, json={"status": "RESOLVED"}).status_code == 403
    login_as(role=UserRole.ADMIN)
    assert client.post(resolve_url, json={"status": "OPEN"}).status_code == 422
    done = client.post(resolve_url, json={"status": "DISMISSED", "note": "Хибна"})
    assert done.status_code == 200
    assert done.json()["status"] == "DISMISSED"
    assert done.json()["resolution_note"] == "Хибна"
    assert client.post(resolve_url, json={"status": "RESOLVED"}).status_code == 409
    missing = f"/api/v1/admin/complaints/{uuid4()}/resolve"
    assert client.post(missing, json={"status": "RESOLVED"}).status_code == 404


# --- Звернення (FR-017) ----------------------------------------------------


def test_feedback_submit_list_and_resolve(client: TestClient, login_as) -> None:
    """[TP-032] [FR-017] Звернення потрапляє до адміністратора і опрацьовується."""
    author = login_as()
    created = client.post(
        "/api/v1/feedback",
        json={"subject": "Пропозиція", "message": "Додайте категорію «Техніка»."},
    )
    assert created.status_code == 201
    feedback_id = created.json()["id"]
    assert client.get("/api/v1/admin/feedback").status_code == 403
    login_as(role=UserRole.ADMIN)
    listed = client.get("/api/v1/admin/feedback").json()
    assert listed[0]["user_email"] == author.email
    assert listed[0]["status"] == "NEW"
    url = f"/api/v1/admin/feedback/{feedback_id}/resolve"
    assert client.post(url).json()["status"] == "RESOLVED"
    assert client.post(url).status_code == 409
    assert client.post(f"/api/v1/admin/feedback/{uuid4()}/resolve").status_code == 404
    assert client.get("/api/v1/admin/feedback?status=NEW").json() == []


def test_feedback_validation_and_auth(client: TestClient, login_as) -> None:
    """[TP-032] [FR-017] [SEC-001] Валідація довжини та вимога сесії."""
    body = {"subject": "Тема", "message": "Достатньо довгий текст."}
    assert client.post("/api/v1/feedback", json=body).status_code == 401
    login_as()
    assert (
        client.post("/api/v1/feedback", json={**body, "subject": "ab"}).status_code
        == 422
    )
    assert (
        client.post("/api/v1/feedback", json={**body, "message": "коротко"}).status_code
        == 422
    )
    assert (
        client.post(
            "/api/v1/feedback", json={**body, "subject": "   ", "message": "x" * 20}
        ).status_code
        == 422
    )


# --- Журнали дій (FR-018) --------------------------------------------------


def test_activity_logs_separate_users_and_admins(
    client: TestClient, login_as, listing_payload
) -> None:
    """[TP-033] [FR-018] Журнали користувачів і адміністраторів окремі."""
    seller = login_as()
    listing_id = _create_listing(client, listing_payload)
    client.patch(f"/api/v1/listings/{listing_id}", json={"title": "Нова назва"})
    client.post(f"/api/v1/favorites/{listing_id}")
    client.delete(f"/api/v1/favorites/{listing_id}")
    client.patch("/api/v1/auth/me", json={"display_name": "Нове Ім'я"})
    login_as()
    _complain(client, listing_id)
    client.post(
        "/api/v1/feedback", json={"subject": "Привіт", "message": "Текст звернення."}
    )
    admin = login_as(role=UserRole.ADMIN)
    client.post(
        f"/api/v1/admin/listings/{listing_id}/withdraw", json={"reason": "Порушення"}
    )
    users = client.get("/api/v1/admin/logs/users")
    assert users.status_code == 200
    actions = {entry["action_type"] for entry in users.json()}
    assert {
        "LISTING_CREATED",
        "LISTING_UPDATED",
        "FAVORITE_ADDED",
        "FAVORITE_REMOVED",
        "PROFILE_UPDATED",
        "COMPLAINT_SUBMITTED",
        "FEEDBACK_SUBMITTED",
    } <= actions
    assert all(entry["actor_id"] != str(admin.user_id) for entry in users.json())
    assert any(entry["actor_email"] == seller.email for entry in users.json())
    admins = client.get("/api/v1/admin/logs/admins").json()
    assert [entry["action_type"] for entry in admins] == ["WITHDRAW_LISTING"]
    assert admins[0]["actor_email"] == admin.email
    assert admins[0]["listing_id"] == listing_id


def test_activity_log_records_listing_withdraw_and_pagination(
    client: TestClient, login_as, listing_payload
) -> None:
    """[TP-033] [FR-018] Зняття власником і пагінація журналу."""
    login_as()
    listing_id = _create_listing(client, listing_payload)
    assert client.delete(f"/api/v1/listings/{listing_id}").status_code == 204
    login_as(role=UserRole.ADMIN)
    everything = client.get("/api/v1/admin/logs/users").json()
    assert [e["action_type"] for e in everything] == [
        "LISTING_WITHDRAWN",
        "LISTING_CREATED",
    ]
    page = client.get("/api/v1/admin/logs/users?skip=1&limit=1").json()
    assert [e["action_type"] for e in page] == ["LISTING_CREATED"]
    assert client.get("/api/v1/admin/logs/users?limit=0").status_code == 422


def test_logs_forbidden_for_non_admin(client: TestClient, login_as) -> None:
    """[TP-033] [FR-018] [SEC-001] Журнали доступні лише ADMIN."""
    assert client.get("/api/v1/admin/logs/users").status_code == 401
    login_as()
    assert client.get("/api/v1/admin/logs/users").status_code == 403
    assert client.get("/api/v1/admin/logs/admins").status_code == 403


def test_admin_log_includes_user_blocks(client: TestClient, login_as) -> None:
    """[TP-033] [FR-018] Блокування користувача видно в журналі адміністраторів."""
    target = login_as()
    login_as(role=UserRole.ADMIN)
    client.post(
        f"/api/v1/admin/users/{target.user_id}/block", json={"reason": BLOCK_REASON}
    )
    entry = client.get("/api/v1/admin/logs/admins").json()[0]
    assert entry["action_type"] == "BLOCK_USER"
    assert entry["target_email"] == target.email
    assert entry["details"] == BLOCK_REASON


# --- Заблоковані користувачі (FR-013) --------------------------------------


def test_blocked_users_list_keeps_reason(client: TestClient, login_as) -> None:
    """[TP-034] [FR-013] Список заблокованих має причину, зникає після розблокування."""
    target = login_as()
    login_as(role=UserRole.ADMIN)
    assert client.get("/api/v1/admin/users/blocked").json() == []
    client.post(
        f"/api/v1/admin/users/{target.user_id}/block", json={"reason": BLOCK_REASON}
    )
    listed = client.get("/api/v1/admin/users/blocked").json()
    assert len(listed) == 1
    assert listed[0]["email"] == target.email
    assert listed[0]["reason"] == BLOCK_REASON
    assert listed[0]["blocked_at"] is not None
    client.post(
        f"/api/v1/admin/users/{target.user_id}/unblock", json={"reason": "Помилка"}
    )
    assert client.get("/api/v1/admin/users/blocked").json() == []


def test_blocked_list_admin_only(client: TestClient, login_as) -> None:
    """[TP-034] [FR-013] [SEC-001] Список заблокованих лише для ADMIN."""
    assert client.get("/api/v1/admin/users/blocked").status_code == 401
    login_as()
    assert client.get("/api/v1/admin/users/blocked").status_code == 403


def test_blocked_status_for_session_of_blocked_user(
    client: TestClient, login_as
) -> None:
    """[TP-034] [FR-013] Користувач бачить факт і причину блокування."""
    target = login_as()
    assert client.get("/api/v1/auth/blocked-status").json() == {
        "is_blocked": False,
        "reason": None,
        "blocked_at": None,
    }
    target.is_blocked = True
    target.block_reason = BLOCK_REASON
    status = client.get("/api/v1/auth/blocked-status").json()
    assert status["is_blocked"] is True
    assert status["reason"] == BLOCK_REASON
    client.cookies.clear()
    assert client.get("/api/v1/auth/blocked-status").json()["is_blocked"] is False
