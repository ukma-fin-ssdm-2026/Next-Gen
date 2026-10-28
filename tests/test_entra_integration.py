"""Модульні тести перетворення MSAL claims."""

from datetime import datetime, timezone
from uuid import UUID

import pytest

from src.config import EntraSettings
from src.integrations.entra import (
    EntraOidcError,
    MsalEntraOidcClient,
    OIDC_SCOPES,
    verified_claims_from_msal,
)
from src.services.auth import InvalidIdentityError


def test_verified_claims_from_msal_maps_stable_entra_identity() -> None:
    """[TP-AUTH-01] [FR-001] [SEC-001]
    Перетворення MSAL claims на стабільну Entra ідентичність.
    """
    expires_at = datetime(2026, 10, 27, tzinfo=timezone.utc)
    claims = verified_claims_from_msal(
        {
            "tid": "11111111-1111-1111-1111-111111111111",
            "oid": "22222222-2222-2222-2222-222222222222",
            "iss": (
                "https://login.microsoftonline.com/"
                "11111111-1111-1111-1111-111111111111/v2.0"
            ),
            "aud": "baraholka-client-id",
            "exp": int(expires_at.timestamp()),
            "preferred_username": "student@ukma.edu.ua",
            "name": "Student NaUKMA",
        }
    )

    assert claims.tenant_id == UUID("11111111-1111-1111-1111-111111111111")
    assert claims.object_id == UUID("22222222-2222-2222-2222-222222222222")
    assert claims.expires_at == expires_at
    assert claims.email == "student@ukma.edu.ua"


def test_verified_claims_from_msal_rejects_missing_stable_object_id() -> None:
    """[TP-AUTH-02] [FR-001] [SEC-001]
    Відхилення токена без обов'язкового oid claim.
    """
    with pytest.raises(InvalidIdentityError) as exc_info:
        verified_claims_from_msal(
            {
                "tid": "11111111-1111-1111-1111-111111111111",
                "iss": "https://issuer.example",
                "aud": "baraholka-client-id",
                "exp": 1_800_000_000,
                "preferred_username": "student@ukma.edu.ua",
            }
        )

    assert str(exc_info.value) == "В ID token відсутні обов'язкові claims"


class FakeMsalClient:
    def __init__(self, *, fail: bool = False) -> None:
        self.fail = fail
        self.scopes: list[str] | None = None

    def initiate_auth_code_flow(
        self,
        *,
        scopes: list[str],
        redirect_uri: str,
    ) -> dict[str, str]:
        self.scopes = scopes
        assert redirect_uri == "http://localhost:8000/api/v1/auth/callback"
        if self.fail:
            raise ValueError("invalid scopes")
        return {"auth_uri": "https://login.microsoftonline.com/auth", "state": "s"}


def _oidc_adapter(fake: FakeMsalClient) -> MsalEntraOidcClient:
    adapter = MsalEntraOidcClient.__new__(MsalEntraOidcClient)
    adapter._settings = EntraSettings(
        tenant_id=UUID("11111111-1111-1111-1111-111111111111"),
        client_id="baraholka-client-id",
        client_secret="test-secret",
        redirect_uri="http://localhost:8000/api/v1/auth/callback",
        frontend_url="http://localhost:5173",
        session_cookie_secure=False,
    )
    adapter._client = fake
    return adapter


def test_oidc_begin_passes_only_non_reserved_scopes_to_msal() -> None:
    """[TP-AUTH-01] [FR-001] [SEC-001]
    Передача лише дозволених scopes у MSAL клієнт.
    """
    fake = FakeMsalClient()

    flow = _oidc_adapter(fake).begin()

    assert flow["state"] == "s"
    assert fake.scopes == OIDC_SCOPES == ["User.Read"]
    assert not {"openid", "profile", "offline_access"} & set(fake.scopes)


def test_oidc_begin_wraps_msal_configuration_error() -> None:
    """[TP-AUTH-01] [FR-001] [SEC-001]
    Обгортання помилок конфігурації MSAL в EntraOidcError.
    """
    with pytest.raises(EntraOidcError, match="Не вдалося розпочати"):
        _oidc_adapter(FakeMsalClient(fail=True)).begin()
