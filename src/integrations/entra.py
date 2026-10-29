"""Адаптер Microsoft Entra ID Authorization Code Flow через MSAL."""

from datetime import datetime, timezone
from typing import Any, Protocol
from uuid import UUID

from src.config import EntraSettings
from src.services.auth import InvalidIdentityError, VerifiedEntraClaims

# MSAL додає зарезервовані OIDC scopes (openid/profile/offline_access) самостійно.
# Явно передаємо лише дозвіл API, інакше initiate_auth_code_flow() кидає ValueError.
OIDC_SCOPES = ["User.Read"]


class EntraOidcError(Exception):
    """Помилка завершення OIDC-потоку."""


class EntraOidcClient(Protocol):
    def begin(self) -> dict[str, Any]:
        """Створює flow з auth_uri і state."""
        ...

    def complete(
        self,
        flow: dict[str, Any],
        auth_response: dict[str, str],
    ) -> VerifiedEntraClaims:
        """Обмінює code та повертає перевірені MSAL claims."""
        ...


class MsalEntraOidcClient:
    """Confidential web client; client secret не потрапляє у browser."""

    def __init__(self, settings: EntraSettings) -> None:
        self._settings = settings
        self._client: Any | None = None

    def _get_client(self) -> Any:
        """Creates the network-aware MSAL client only for a real Entra flow."""
        if self._client is None:
            from msal import ConfidentialClientApplication

            self._client = ConfidentialClientApplication(
                client_id=self._settings.client_id,
                client_credential=self._settings.client_secret,
                authority=self._settings.authority,
            )
        return self._client

    def begin(self) -> dict[str, Any]:
        try:
            flow = self._get_client().initiate_auth_code_flow(
                scopes=OIDC_SCOPES,
                redirect_uri=self._settings.redirect_uri,
            )
        except ValueError as exc:
            raise EntraOidcError("Не вдалося розпочати вхід Microsoft") from exc
        if "auth_uri" not in flow or "state" not in flow:
            raise EntraOidcError("Не вдалося розпочати вхід Microsoft")
        return flow

    def complete(
        self,
        flow: dict[str, Any],
        auth_response: dict[str, str],
    ) -> VerifiedEntraClaims:
        try:
            result = self._get_client().acquire_token_by_auth_code_flow(
                flow,
                auth_response,
            )
        except ValueError as exc:
            raise EntraOidcError("Невалідний state або nonce") from exc

        if "error" in result:
            raise EntraOidcError("Вхід Microsoft відхилено")
        claims = result.get("id_token_claims")
        if not isinstance(claims, dict):
            raise EntraOidcError("Відповідь Microsoft не містить ID token claims")
        return verified_claims_from_msal(claims)


def verified_claims_from_msal(claims: dict[str, Any]) -> VerifiedEntraClaims:
    """Перетворює вже криптографічно перевірені MSAL claims."""
    try:
        email = claims.get("email") or claims["preferred_username"]
        display_name = claims.get("name") or email
        return VerifiedEntraClaims(
            tenant_id=UUID(str(claims["tid"])),
            object_id=UUID(str(claims["oid"])),
            issuer=str(claims["iss"]),
            audience=str(claims["aud"]),
            expires_at=datetime.fromtimestamp(int(claims["exp"]), tz=timezone.utc),
            email=str(email),
            display_name=str(display_name),
        )
    except (KeyError, TypeError, ValueError, OverflowError) as exc:
        raise InvalidIdentityError("В ID token відсутні обов'язкові claims") from exc
