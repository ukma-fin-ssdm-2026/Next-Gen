"""Інтеграційні тести HTTP-межі Microsoft Entra ID."""

from datetime import datetime, timedelta, timezone
from typing import Any
from uuid import UUID

import pytest
from fastapi.testclient import TestClient

from src.api.deps import (
    get_auth_service,
    get_auth_session_store,
    get_entra_oidc_client,
    get_entra_settings,
    get_oidc_flow_store,
)
from src.api.main import app
from src.config import EntraSettings
from src.repositories.users import InMemoryUserRepository
from src.services.auth import AuthService, EntraAuthConfig, VerifiedEntraClaims
from src.services.auth_sessions import InMemoryAuthSessionStore, InMemoryOidcFlowStore

TENANT_ID = UUID("11111111-1111-1111-1111-111111111111")
OBJECT_ID = UUID("22222222-2222-2222-2222-222222222222")
CLIENT_ID = "baraholka-client-id"
ISSUER = f"https://login.microsoftonline.com/{TENANT_ID}/v2.0"


class FakeEntraOidcClient:
    def __init__(self, claims: VerifiedEntraClaims) -> None:
        self.claims = claims
        self.completed_response: dict[str, str] | None = None

    def begin(self) -> dict[str, Any]:
        return {
            "auth_uri": "https://login.microsoftonline.com/authorize?client_id=test",
            "state": "state-created-by-msal",
            "nonce": "nonce-created-by-msal",
        }

    def complete(
        self,
        flow: dict[str, Any],
        auth_response: dict[str, str],
    ) -> VerifiedEntraClaims:
        assert flow["state"] == "state-created-by-msal"
        self.completed_response = auth_response
        return self.claims


@pytest.fixture
def auth_http_client(monkeypatch):
    monkeypatch.setenv("DEV_AUTH_ENABLED", "false")
    settings = EntraSettings(
        tenant_id=TENANT_ID,
        client_id=CLIENT_ID,
        client_secret="test-secret-not-used-by-fake",
        redirect_uri="http://localhost:8000/api/v1/auth/callback",
        frontend_url="http://localhost:5173",
        session_cookie_secure=False,
    )
    claims = VerifiedEntraClaims(
        tenant_id=TENANT_ID,
        object_id=OBJECT_ID,
        issuer=ISSUER,
        audience=CLIENT_ID,
        expires_at=datetime.now(timezone.utc) + timedelta(minutes=30),
        email="student@ukma.edu.ua",
        display_name="Student NaUKMA",
    )
    repository = InMemoryUserRepository()
    service = AuthService(
        repository,
        EntraAuthConfig(
            tenant_id=TENANT_ID,
            issuer=ISSUER,
            audience=CLIENT_ID,
        ),
    )
    oidc = FakeEntraOidcClient(claims)
    flows = InMemoryOidcFlowStore()
    sessions = InMemoryAuthSessionStore()

    app.dependency_overrides[get_entra_settings] = lambda: settings
    app.dependency_overrides[get_entra_oidc_client] = lambda: oidc
    app.dependency_overrides[get_oidc_flow_store] = lambda: flows
    app.dependency_overrides[get_auth_session_store] = lambda: sessions
    app.dependency_overrides[get_auth_service] = lambda: service
    with TestClient(app) as client:
        yield client, oidc, repository, sessions
    app.dependency_overrides.clear()


def test_login_callback_me_and_logout_complete_local_session_cycle(
    auth_http_client,
) -> None:
    """[TP-AUTH-01] [FR-001] [SEC-001]
    Повний цикл входу через OIDC, локальної сесії та logout.
    """
    client, oidc, _, _ = auth_http_client

    login_response = client.get(
        "/api/v1/auth/login?next=/favorites%3Fsort%3Dnewest",
        follow_redirects=False,
    )

    assert login_response.status_code == 307
    assert login_response.headers["location"].startswith(
        "https://login.microsoftonline.com/"
    )
    assert client.cookies.get("baraholka_oidc_state") == "state-created-by-msal"
    assert "HttpOnly" in login_response.headers["set-cookie"]
    assert "SameSite=lax" in login_response.headers["set-cookie"]

    callback_response = client.get(
        "/api/v1/auth/callback?code=authorization-code&state=state-created-by-msal",
        follow_redirects=False,
    )

    assert callback_response.status_code == 303
    assert callback_response.headers["location"] == (
        "http://localhost:5173/favorites?sort=newest"
    )
    assert oidc.completed_response == {
        "code": "authorization-code",
        "state": "state-created-by-msal",
    }
    assert client.cookies.get("baraholka_session") is not None
    assert "HttpOnly" in callback_response.headers["set-cookie"]
    assert "SameSite=lax" in callback_response.headers["set-cookie"]

    me_response = client.get("/api/v1/auth/me")

    assert me_response.status_code == 200
    assert me_response.json()["email"] == "student@ukma.edu.ua"
    assert me_response.json()["role"] == "USER"

    logout_response = client.post("/api/v1/auth/logout")

    assert logout_response.status_code == 204
    assert client.get("/api/v1/auth/me").status_code == 401


def test_development_login_creates_real_local_session(
    auth_http_client,
    monkeypatch,
) -> None:
    """[FR-001] Dev login still uses the normal server-side session path."""
    client, _, _, _ = auth_http_client
    monkeypatch.setenv("APP_ENV", "development")
    monkeypatch.setenv("DEV_AUTH_ENABLED", "true")
    app.dependency_overrides.pop(get_entra_oidc_client)

    response = client.get(
        "/api/v1/auth/login?next=/favorites",
        follow_redirects=False,
    )

    assert response.status_code == 307
    assert response.headers["location"] == "/favorites"
    assert client.cookies.get("baraholka_session") is not None
    assert client.cookies.get("baraholka_oidc_state") is None

    me_response = client.get("/api/v1/auth/me")
    assert me_response.status_code == 200
    assert me_response.json() == {
        "user_id": me_response.json()["user_id"],
        "email": "developer@ukma.edu.ua",
        "display_name": "Local Developer",
        "role": "USER",
    }


def test_development_login_is_rejected_outside_local_development(
    auth_http_client,
    monkeypatch,
) -> None:
    """[SEC-001] A production process cannot enable the local identity shortcut."""
    client, _, _, _ = auth_http_client
    monkeypatch.setenv("APP_ENV", "production")
    monkeypatch.setenv("DEV_AUTH_ENABLED", "true")

    response = client.get("/api/v1/auth/login", follow_redirects=False)

    assert response.status_code == 503
    assert "APP_ENV=development" in response.json()["detail"]


@pytest.mark.parametrize(
    "next_url",
    [
        "https://evil.example/phishing",
        "//evil.example/phishing",
        r"/\evil.example/phishing",
    ],
)
def test_login_does_not_redirect_to_external_next_url(
    auth_http_client,
    next_url: str,
) -> None:
    """[SEC-001] Зовнішній next URL не створює open redirect."""
    client, _, _, _ = auth_http_client

    client.get(
        "/api/v1/auth/login",
        params={"next": next_url},
        follow_redirects=False,
    )
    response = client.get(
        "/api/v1/auth/callback?code=authorization-code&state=state-created-by-msal",
        follow_redirects=False,
    )

    assert response.status_code == 303
    assert response.headers["location"] == "http://localhost:5173"


def test_callback_rejects_state_that_does_not_match_cookie(auth_http_client) -> None:
    """[TP-AUTH-03] [FR-001] [SEC-001]
    Відхилення OIDC callback при невідповідності state.
    """
    client, oidc, _, _ = auth_http_client
    client.get("/api/v1/auth/login", follow_redirects=False)

    response = client.get(
        "/api/v1/auth/callback?code=authorization-code&state=attacker-state",
        follow_redirects=False,
    )

    assert response.status_code == 400
    assert response.json() == {"detail": "Невалідний OIDC state"}
    assert oidc.completed_response is None


def test_me_requires_server_side_session(auth_http_client) -> None:
    """[TP-AUTH-01] [FR-001] [SEC-001] Отримання профілю /me вимагає серверної сесії."""
    client, _, _, _ = auth_http_client

    response = client.get("/api/v1/auth/me")

    assert response.status_code == 401
    assert response.json() == {"detail": "Потрібен вхід через Microsoft"}


def test_callback_flow_cannot_be_replayed(auth_http_client) -> None:
    """[TP-AUTH-03] [FR-001] [SEC-001] Захист від повторного використання OIDC flow."""
    client, _, _, _ = auth_http_client
    client.get("/api/v1/auth/login", follow_redirects=False)
    callback_url = (
        "/api/v1/auth/callback?code=authorization-code" "&state=state-created-by-msal"
    )

    first_response = client.get(callback_url, follow_redirects=False)
    client.cookies.set("baraholka_oidc_state", "state-created-by-msal")
    replay_response = client.get(callback_url, follow_redirects=False)

    assert first_response.status_code == 303
    assert replay_response.status_code == 400
    assert replay_response.json() == {
        "detail": "OIDC flow не знайдено або він завершився"
    }


def test_blocked_user_loses_existing_session(auth_http_client) -> None:
    """[TP-AUTH-01] [FR-001] [SEC-001] Заблокований користувач втрачає сесію (403)."""
    client, _, repository, _ = auth_http_client
    client.get("/api/v1/auth/login", follow_redirects=False)
    client.get(
        "/api/v1/auth/callback?code=authorization-code" "&state=state-created-by-msal",
        follow_redirects=False,
    )
    user = repository.get_by_entra_identity(TENANT_ID, OBJECT_ID)
    assert user is not None
    user.is_blocked = True

    response = client.get("/api/v1/auth/me")

    assert response.status_code == 403
    assert response.json() == {"detail": "Обліковий запис користувача заблоковано"}
    user.is_blocked = False
    assert client.get("/api/v1/auth/me").status_code == 401


def test_login_returns_503_when_entra_configuration_is_missing(monkeypatch) -> None:
    """[TP-AUTH-01] [FR-001] [SEC-001] Відсутність конфігурації Entra повертає 503."""
    for name in (
        "MICROSOFT_TENANT_ID",
        "MICROSOFT_CLIENT_ID",
        "MICROSOFT_CLIENT_SECRET",
        "MICROSOFT_REDIRECT_URI",
    ):
        monkeypatch.delenv(name, raising=False)

    with TestClient(app) as client:
        response = client.get("/api/v1/auth/login", follow_redirects=False)

    assert response.status_code == 503
    assert response.json() == {"detail": "Microsoft Entra ID ще не сконфігуровано"}
