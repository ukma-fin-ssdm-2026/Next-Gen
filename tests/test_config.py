"""Тести безпечної конфігурації Microsoft Entra ID."""

import pytest

from src.config import ConfigurationError, EntraSettings

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
    _set_valid_env(monkeypatch)

    settings = EntraSettings.from_env()

    assert settings.session_cookie_secure is False


def test_non_local_redirect_uri_requires_https(monkeypatch: pytest.MonkeyPatch) -> None:
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
    _set_valid_env(monkeypatch)
    monkeypatch.setenv(
        "MICROSOFT_REDIRECT_URI",
        "https://baraholka.example/api/v1/auth/callback",
    )
    monkeypatch.setenv("SESSION_COOKIE_SECURE", "false")

    with pytest.raises(ConfigurationError, match="SESSION_COOKIE_SECURE=true"):
        EntraSettings.from_env()
