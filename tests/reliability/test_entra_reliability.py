"""Тести надійності (Reliability Tests) для адаптера Microsoft Entra OIDC (Лаб 9).

Охоплює три обов'язкові категорії з Лабораторної роботи 9 та Бонус 1:
1. Тест обробки помилки (Error handling): система не падає при винятку/помилковій
   відповіді провайдера і повертає зрозумілий контрольований виняток EntraOidcError.
2. Тест зовнішньої відмови / ін'єкція збою (Fault injection): тестовий дублер
   імітує тайм-аут або обрив з'єднання з Microsoft Entra ID; перевіряється
   швидка відмова (fail-fast), логування та HTTP 502/401 замість 500.
3. Граничний тест (Boundary test): перевірка захисних умов (guard clauses)
   для межових і некоректних вхідних параметрів (timeout <= 0, max_attempts < 1,
   порожні або невалідні структури flow/auth_response).
4. Бонус 1 (Backoff + Full Jitter): перевірка обмежених повторів ідемпотентного
   виклику `begin()` з експоненційним відступом та повним джитером, складених
   із тайм-аутом у порядку §3.5.
"""

import logging
from typing import Any
from uuid import UUID

from fastapi.testclient import TestClient
import pytest
from requests.exceptions import ConnectionError as RequestsConnectionError, Timeout

from src.api.deps import get_entra_oidc_client, get_entra_settings
from src.api.main import app
from src.config import EntraSettings
from src.integrations.entra import (
    EntraOidcError,
    MsalEntraOidcClient,
    compute_full_jitter_backoff,
)


def _make_settings() -> EntraSettings:
    return EntraSettings(
        tenant_id=UUID("11111111-1111-1111-1111-111111111111"),
        client_id="baraholka-client-id",
        client_secret="test-secret",
        redirect_uri="http://localhost:8000/api/v1/auth/callback",
        frontend_url="http://localhost:5173",
        session_cookie_secure=False,
    )


class _FaultInjectingMsalClient:
    """Тестовий дублер MSAL, що ін'єктує мережеві збої або некоректні відповіді."""

    def __init__(
        self,
        *,
        begin_exc: Exception | None = None,
        begin_side_effects: list[Any] | None = None,
        complete_exc: Exception | None = None,
        begin_return: Any = None,
        complete_return: Any = None,
    ) -> None:
        self._begin_exc = begin_exc
        self._begin_side_effects = list(begin_side_effects or [])
        self._complete_exc = complete_exc
        self._begin_return = begin_return
        self._complete_return = complete_return
        self.begin_calls = 0
        self.complete_calls = 0

    def initiate_auth_code_flow(
        self,
        *,
        scopes: list[str],
        redirect_uri: str,
    ) -> Any:
        self.begin_calls += 1
        if self._begin_side_effects:
            effect = self._begin_side_effects.pop(0)
            if isinstance(effect, Exception):
                raise effect
            return effect
        if self._begin_exc is not None:
            raise self._begin_exc
        return self._begin_return

    def acquire_token_by_auth_code_flow(
        self,
        flow: dict[str, Any],
        auth_response: dict[str, str],
    ) -> Any:
        self.complete_calls += 1
        if self._complete_exc is not None:
            raise self._complete_exc
        return self._complete_return


def _client_with_double(
    double: _FaultInjectingMsalClient,
    *,
    max_attempts: int = 3,
    base_backoff: float = 0.2,
    recorded_sleeps: list[float] | None = None,
) -> MsalEntraOidcClient:
    sleeps = recorded_sleeps if recorded_sleeps is not None else []
    adapter = MsalEntraOidcClient(
        _make_settings(),
        timeout=3.0,
        max_attempts=max_attempts,
        base_backoff=base_backoff,
        sleep_fn=sleeps.append,
    )
    adapter._client = double
    return adapter


# ---------------------------------------------------------------------------
# 1. Тест обробки помилки (Error Handling Test)
# ---------------------------------------------------------------------------


def test_entra_complete_handles_rejected_or_malformed_token_response_gracefully() -> (
    None
):
    """[TP-AUTH-01] [FR-001] [SEC-001]
    Тест обробки помилки: при відмові входу або відсутності id_token_claims
    адаптер підіймає контрольований EntraOidcError замість KeyError/TypeError.
    """
    valid_flow = {"state": "state-1", "auth_uri": "https://login.microsoftonline.com"}
    valid_auth_response = {"code": "auth-code", "state": "state-1"}

    rejected_client = _client_with_double(
        _FaultInjectingMsalClient(
            complete_return={
                "error": "access_denied",
                "error_description": "User cancelled",
            }
        )
    )
    with pytest.raises(EntraOidcError, match="Вхід Microsoft відхилено"):
        rejected_client.complete(valid_flow, valid_auth_response)

    malformed_client = _client_with_double(
        _FaultInjectingMsalClient(complete_return={"access_token": "opaque-only"})
    )
    with pytest.raises(
        EntraOidcError,
        match="Відповідь Microsoft не містить ID token claims",
    ):
        malformed_client.complete(valid_flow, valid_auth_response)

    non_dict_client = _client_with_double(
        _FaultInjectingMsalClient(complete_return=None)
    )
    with pytest.raises(
        EntraOidcError,
        match="Відповідь Microsoft не містить ID token claims",
    ):
        non_dict_client.complete(valid_flow, valid_auth_response)


# ---------------------------------------------------------------------------
# 2. Тест зовнішньої відмови / Ін'єкція збою (Fault Injection Test)
# ---------------------------------------------------------------------------


def test_entra_fault_injection_network_timeout_and_connection_error(
    caplog: pytest.LogCaptureFixture,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """[TP-AUTH-01] [FR-001] [SEC-001]
    Ін'єкція збою: імітація тайм-ауту та обриву з'єднання з Microsoft Entra ID.
    Перевіряє логування збою, перехоплення RequestException та HTTP 502 замість 500.
    """
    monkeypatch.setenv("DEV_AUTH_ENABLED", "false")
    caplog.set_level(logging.WARNING)

    double = _FaultInjectingMsalClient(
        begin_exc=Timeout("Read timed out after 5.0 seconds"),
        complete_exc=RequestsConnectionError(
            "DNS lookup failed for login.microsoftonline.com"
        ),
    )
    timeout_adapter = _client_with_double(double, max_attempts=3)

    with pytest.raises(
        EntraOidcError,
        match="Сервіс автентифікації Microsoft тимчасово недоступний",
    ):
        timeout_adapter.begin()

    assert "Помилка мережі при ініціалізації входу через Microsoft Entra" in caplog.text

    with pytest.raises(
        EntraOidcError,
        match="Сервіс автентифікації Microsoft тимчасово недоступний",
    ):
        timeout_adapter.complete(
            {"state": "s1", "auth_uri": "https://login.microsoftonline.com"},
            {"code": "c1", "state": "s1"},
        )

    assert "Помилка мережі при завершенні входу через Microsoft Entra" in caplog.text

    # Перевірка на рівні HTTP роутера: /api/v1/auth/login повертає 502 замість 500
    app.dependency_overrides[get_entra_settings] = _make_settings
    app.dependency_overrides[get_entra_oidc_client] = lambda: timeout_adapter
    try:
        with TestClient(app, raise_server_exceptions=False) as http_client:
            response = http_client.get("/api/v1/auth/login", follow_redirects=False)
        assert response.status_code == 502
        assert response.json() == {
            "detail": "Сервіс автентифікації Microsoft тимчасово недоступний"
        }
    finally:
        app.dependency_overrides.clear()


# ---------------------------------------------------------------------------
# 3. Бонус 1: Обмежені повтори з експоненційним відступом і Full Jitter (§3.3, §3.5)
# ---------------------------------------------------------------------------


def test_entra_begin_retries_with_exponential_backoff_and_full_jitter_are_bounded() -> (
    None
):
    """[TP-AUTH-01] [FR-001] [SEC-001]
    Бонус 1: доводить, що при постійному мережевому збої кількість спроб суворо
    обмежена (`max_attempts=3`), між ними застосовується full jitter backoff,
    а після останньої спроби спрацьовує обрана реакція (`EntraOidcError`).
    """
    recorded_sleeps: list[float] = []
    double = _FaultInjectingMsalClient(
        begin_exc=Timeout("Entra metadata endpoint timed out")
    )
    adapter = _client_with_double(
        double,
        max_attempts=3,
        base_backoff=0.2,
        recorded_sleeps=recorded_sleeps,
    )

    with pytest.raises(
        EntraOidcError,
        match="Сервіс автентифікації Microsoft тимчасово недоступний",
    ):
        adapter.begin()

    # Кількість спроб суворо обмежена 3, паузи робляться лише між спробами (2 рази)
    assert double.begin_calls == 3
    assert len(recorded_sleeps) == 2
    assert 0.0 <= recorded_sleeps[0] <= 0.2
    assert 0.0 <= recorded_sleeps[1] <= 0.4


def test_entra_begin_recovers_on_transient_failure_before_max_attempts() -> None:
    """[TP-AUTH-01] [FR-001] [SEC-001]
    Бонус 1: якщо перші дві спроби падають через тимчасовий мережевий збій,
    а третя повертає валідний flow, операція успішно відновлюється.
    """
    recorded_sleeps: list[float] = []
    expected_flow = {
        "auth_uri": "https://login.microsoftonline.com/authorize",
        "state": "recovered-state",
    }
    double = _FaultInjectingMsalClient(
        begin_side_effects=[
            Timeout("Attempt 1 timed out"),
            RequestsConnectionError("Attempt 2 connection reset"),
            expected_flow,
        ]
    )
    adapter = _client_with_double(
        double,
        max_attempts=3,
        base_backoff=0.2,
        recorded_sleeps=recorded_sleeps,
    )

    flow = adapter.begin()

    assert flow == expected_flow
    assert double.begin_calls == 3
    assert len(recorded_sleeps) == 2


# ---------------------------------------------------------------------------
# 4. Граничний тест (Boundary Test)
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("invalid_timeout", [0, 0.0, -0.1, -5.0])
def test_entra_boundary_rejects_non_positive_timeout(invalid_timeout: float) -> None:
    """[TP-AUTH-01] [FR-001] [SEC-001]
    Граничний тест: ініціалізація клієнта з нульовим або від'ємним тайм-аутом
    відхиляється захисною перевіркою (guard clause).
    """
    with pytest.raises(
        ValueError,
        match="HTTP timeout для Entra ID має бути більшим за 0",
    ):
        MsalEntraOidcClient(_make_settings(), timeout=invalid_timeout)


def test_entra_boundary_rejects_invalid_retry_or_backoff_parameters() -> None:
    """[TP-AUTH-01] [FR-001] [SEC-001]
    Граничний тест: перевірка guard clauses для max_attempts < 1, base_backoff < 0
    та граничних значень compute_full_jitter_backoff.
    """
    with pytest.raises(ValueError, match="max_attempts має бути не меншою за 1"):
        MsalEntraOidcClient(_make_settings(), max_attempts=0)

    with pytest.raises(ValueError, match="base_backoff не може бути від'ємною"):
        MsalEntraOidcClient(_make_settings(), base_backoff=-0.01)

    with pytest.raises(ValueError, match="attempt не може бути від'ємним"):
        compute_full_jitter_backoff(-1)

    assert (
        compute_full_jitter_backoff(
            2,
            base_delay=0.25,
            max_delay=2.0,
            uniform_fn=lambda low, high: high,
        )
        == 1.0
    )


@pytest.mark.parametrize(
    ("flow_input", "auth_response_input"),
    [
        ({}, {"code": "abc", "state": "s"}),
        (None, {"code": "abc", "state": "s"}),
        ({"state": "s"}, {}),
        ({"state": "s"}, None),
    ],
)
def test_entra_boundary_rejects_empty_or_non_dict_flow_and_response(
    flow_input: Any,
    auth_response_input: Any,
) -> None:
    """[TP-AUTH-03] [FR-001] [SEC-001]
    Граничний тест: порожні або невалідні структури flow та auth_response
    відхиляються guard-перевірками до звернення у мережу.
    """
    adapter = _client_with_double(_FaultInjectingMsalClient())

    with pytest.raises(EntraOidcError, match="Невалідний state або nonce"):
        adapter.complete(flow_input, auth_response_input)
