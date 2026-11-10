"""Адаптер Microsoft Entra ID Authorization Code Flow через MSAL."""

from collections.abc import Callable
from datetime import datetime, timezone
import logging
import secrets
import time
from typing import Any, Protocol
from uuid import UUID

from requests import RequestException

from src.config import EntraSettings
from src.services.auth import InvalidIdentityError, VerifiedEntraClaims

logger = logging.getLogger(__name__)
_SYSTEM_RANDOM = secrets.SystemRandom()

# MSAL додає зарезервовані OIDC scopes (openid/profile/offline_access) самостійно.
# Явно передаємо лише дозвіл API, інакше initiate_auth_code_flow() кидає ValueError.
OIDC_SCOPES = ["User.Read"]
ENTRA_HTTP_TIMEOUT_SECONDS = 5.0
ENTRA_MAX_RETRY_ATTEMPTS = 3
ENTRA_BASE_BACKOFF_SECONDS = 0.2
ENTRA_MAX_BACKOFF_SECONDS = 2.0


class EntraOidcError(Exception):
    """Помилка завершення OIDC-потоку."""


def compute_full_jitter_backoff(
    attempt: int,
    *,
    base_delay: float = ENTRA_BASE_BACKOFF_SECONDS,
    max_delay: float = ENTRA_MAX_BACKOFF_SECONDS,
    uniform_fn: Callable[[float, float], float] | None = None,
) -> float:
    """Обчислює затримку за алгоритмом Exponential Backoff + Full Jitter (§3.3).

    Для спроби `attempt` (0-індексованої) верхня межа становить
    `min(max_delay, base_delay * 2**attempt)`, а фактична пауза обирається
    рівномірно на відрізку `[0, cap]`.
    """
    if attempt < 0:
        raise ValueError("Номер спроби attempt не може бути від'ємним")
    if base_delay < 0 or max_delay < 0:
        raise ValueError("Параметри затримки backoff не можуть бути від'ємними")
    cap = min(max_delay, base_delay * (2**attempt))
    chooser = uniform_fn if uniform_fn is not None else _SYSTEM_RANDOM.uniform
    return float(chooser(0.0, cap))


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

    _timeout: float = ENTRA_HTTP_TIMEOUT_SECONDS
    _max_attempts: int = ENTRA_MAX_RETRY_ATTEMPTS
    _base_backoff: float = ENTRA_BASE_BACKOFF_SECONDS
    _sleep_fn: Callable[[float], None] = staticmethod(time.sleep)

    def __init__(
        self,
        settings: EntraSettings,
        *,
        timeout: float = ENTRA_HTTP_TIMEOUT_SECONDS,
        max_attempts: int = ENTRA_MAX_RETRY_ATTEMPTS,
        base_backoff: float = ENTRA_BASE_BACKOFF_SECONDS,
        sleep_fn: Callable[[float], None] = time.sleep,
    ) -> None:
        if timeout <= 0:
            raise ValueError("HTTP timeout для Entra ID має бути більшим за 0")
        if max_attempts < 1:
            raise ValueError("Кількість спроб max_attempts має бути не меншою за 1")
        if base_backoff < 0:
            raise ValueError("Базова затримка base_backoff не може бути від'ємною")
        self._settings = settings
        self._timeout = timeout
        self._max_attempts = max_attempts
        self._base_backoff = base_backoff
        self._sleep_fn = sleep_fn
        self._client: Any | None = None

    def _get_client(self) -> Any:
        """Creates the network-aware MSAL client only for a real Entra flow."""
        if self._client is None:
            from msal import ConfidentialClientApplication

            self._client = ConfidentialClientApplication(
                client_id=self._settings.client_id,
                client_credential=self._settings.client_secret,
                authority=self._settings.authority,
                timeout=self._timeout,
            )
        return self._client

    def begin(self) -> dict[str, Any]:
        """Ініціює ідемпотентний OIDC flow з композицією патернів (§3.5):
        1. Внутрішній шар: HTTP timeout на кожен виклик (`self._timeout`).
        2. Середній шар: обмежені повтори (`self._max_attempts`) з експоненційним
           відступом і повним джитером (Full Jitter) при мережевих збоях.
        3. Зовнішній шар: логування та контрольована швидка відмова (`EntraOidcError`).
        """
        flow: Any = None

        for attempt in range(self._max_attempts):
            try:
                flow = self._get_client().initiate_auth_code_flow(
                    scopes=OIDC_SCOPES,
                    redirect_uri=self._settings.redirect_uri,
                )
                break
            except ValueError as exc:
                raise EntraOidcError("Не вдалося розпочати вхід Microsoft") from exc
            except (RequestException, OSError) as exc:
                is_last_attempt = attempt + 1 >= self._max_attempts
                if is_last_attempt:
                    logger.warning(
                        "Помилка мережі при ініціалізації входу через Microsoft Entra "
                        "(вичерпано %d спроб): %s",
                        self._max_attempts,
                        exc,
                    )
                    raise EntraOidcError(
                        "Сервіс автентифікації Microsoft тимчасово недоступний"
                    ) from exc

                delay = compute_full_jitter_backoff(
                    attempt,
                    base_delay=self._base_backoff,
                )
                logger.info(
                    "Тимчасовий збій мережі Microsoft Entra (спроба %d/%d), "
                    "повтор через %.3f с: %s",
                    attempt + 1,
                    self._max_attempts,
                    delay,
                    exc,
                )
                self._sleep_fn(delay)

        if not isinstance(flow, dict) or "auth_uri" not in flow or "state" not in flow:
            raise EntraOidcError("Не вдалося розпочати вхід Microsoft")
        return flow

    def complete(
        self,
        flow: dict[str, Any],
        auth_response: dict[str, str],
    ) -> VerifiedEntraClaims:
        if not isinstance(flow, dict) or not flow:
            raise EntraOidcError("Невалідний state або nonce")
        if not isinstance(auth_response, dict) or not auth_response:
            raise EntraOidcError("Невалідний state або nonce")

        try:
            result = self._get_client().acquire_token_by_auth_code_flow(
                flow,
                auth_response,
            )
        except ValueError as exc:
            raise EntraOidcError("Невалідний state або nonce") from exc
        except (RequestException, OSError) as exc:
            logger.warning(
                "Помилка мережі при завершенні входу через Microsoft Entra: %s",
                exc,
            )
            raise EntraOidcError(
                "Сервіс автентифікації Microsoft тимчасово недоступний"
            ) from exc

        if not isinstance(result, dict):
            raise EntraOidcError("Відповідь Microsoft не містить ID token claims")
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
