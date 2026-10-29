"""Тести безпечної конфігурації Microsoft Entra ID та сховища зображень."""

from pathlib import Path

import pytest

from src.api import deps
from src.config import (
    ConfigurationError,
    EntraSettings,
    get_admin_emails,
    get_image_storage_dir,
)
from src.repositories.image_storage import LocalImageStorage

VALID_ENV = {
    "MICROSOFT_TENANT_ID": "11111111-1111-1111-1111-111111111111",
    "MICROSOFT_CLIENT_ID": "baraholka-client-id",
    "MICROSOFT_CLIENT_SECRET": "not-a-real-secret",
    "MICROSOFT_REDIRECT_URI": "http://localhost:8000/api/v1/auth/callback",
    "FRONTEND_URL": "http://localhost:5173",
}


def _set_valid_env(monkeypatch: pytest.MonkeyPatch) -> None:
    for name, value in VALID_ENV.items():
        monkeypatch.setenv(name, value)
    monkeypatch.delenv("SESSION_COOKIE_SECURE", raising=False)


def test_localhost_http_configuration_uses_non_secure_development_cookie(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """[TP-AUTH-01] [FR-001] [SEC-001]
    Localhost HTTP конфігурація використовує cookie розробки.
    """
    _set_valid_env(monkeypatch)

    settings = EntraSettings.from_env()

    assert settings.session_cookie_secure is False


def test_non_local_redirect_uri_requires_https(monkeypatch: pytest.MonkeyPatch) -> None:
    """[TP-AUTH-01] [FR-001] [SEC-001]
    Не-локальний redirect_uri вимагає обов'язкового HTTPS протоколу.
    """
    _set_valid_env(monkeypatch)
    monkeypatch.setenv(
        "MICROSOFT_REDIRECT_URI",
        "http://baraholka.example/api/v1/auth/callback",
    )

    with pytest.raises(ConfigurationError, match="HTTPS"):
        EntraSettings.from_env()


def test_https_redirect_cannot_disable_secure_cookie(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """[TP-AUTH-01] [FR-001] [SEC-001]
    HTTPS redirect_uri блокує вимкнення захищених session cookies.
    """
    _set_valid_env(monkeypatch)
    monkeypatch.setenv(
        "MICROSOFT_REDIRECT_URI",
        "https://baraholka.example/api/v1/auth/callback",
    )
    monkeypatch.setenv("SESSION_COOKIE_SECURE", "false")

    with pytest.raises(ConfigurationError, match="SESSION_COOKIE_SECURE=true"):
        EntraSettings.from_env()


def test_production_di_wires_local_image_storage() -> None:
    """[TP-022] [FR-002] Production DI підключає LocalImageStorage за замовчуванням."""
    assert isinstance(deps.image_storage, LocalImageStorage)
    assert deps.get_image_storage() is deps.image_storage


def test_get_image_storage_dir_respects_env(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """[TP-022] [FR-002]
    get_image_storage_dir використовує IMAGE_STORAGE_DIR з оточення.
    """
    custom_dir = tmp_path / "custom-uploads"
    monkeypatch.setenv("IMAGE_STORAGE_DIR", str(custom_dir))
    assert get_image_storage_dir() == custom_dir


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        (None, frozenset()),
        ("", frozenset()),
        (
            " A@ukma.edu.ua, b@UKMA.edu.ua;a@ukma.edu.ua\nc@ukma.edu.ua ",
            frozenset({"a@ukma.edu.ua", "b@ukma.edu.ua", "c@ukma.edu.ua"}),
        ),
    ],
)
def test_admin_emails_are_parsed_and_normalized(
    monkeypatch: pytest.MonkeyPatch, raw: str | None, expected: frozenset[str]
) -> None:
    """[TP-AUTH-05] [FR-001] [SEC-001] ADMIN_EMAILS нормалізується й дедуплікується."""
    if raw is None:
        monkeypatch.delenv("ADMIN_EMAILS", raising=False)
    else:
        monkeypatch.setenv("ADMIN_EMAILS", raw)
    assert get_admin_emails() == expected


@pytest.mark.parametrize("raw", ["a@gmail.com", "ukma.edu.ua", "@ukma.edu.ua"])
def test_admin_emails_reject_foreign_or_malformed_addresses(
    monkeypatch: pytest.MonkeyPatch, raw: str
) -> None:
    """[TP-AUTH-05] [FR-001] [SEC-001]
    Адреса не з @ukma.edu.ua у ADMIN_EMAILS зупиняє конфігурацію.
    """
    monkeypatch.setenv("ADMIN_EMAILS", raw)
    with pytest.raises(ConfigurationError):
        get_admin_emails()


def test_invalid_admin_emails_make_auth_service_unavailable(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """[TP-AUTH-05] [FR-001] [SEC-001]
    Некоректний ADMIN_EMAILS не дає тихо працювати з порожнім списком (503).
    """
    _set_valid_env(monkeypatch)
    monkeypatch.setenv("ADMIN_EMAILS", "a@gmail.com")
    with pytest.raises(deps.HTTPException) as caught:
        deps.get_auth_service(EntraSettings.from_env())
    assert caught.value.status_code == 503
