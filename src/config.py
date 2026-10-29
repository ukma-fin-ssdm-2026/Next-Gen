"""Конфігурація застосунку зі змінних середовища."""

from dataclasses import dataclass
import os
from pathlib import Path
import tempfile
from urllib.parse import urlparse
from uuid import UUID


class ConfigurationError(RuntimeError):
    """Обов'язкова конфігурація відсутня або некоректна."""


def _required(name: str) -> str:
    value = os.getenv(name, "").strip()
    if not value:
        raise ConfigurationError(f"Не задано {name}")
    return value


def _validate_url(value: str, name: str, *, allow_local_http: bool) -> str:
    parsed = urlparse(value)
    if not parsed.scheme or not parsed.netloc:
        raise ConfigurationError(f"{name} має бути абсолютним URL")
    is_local = parsed.hostname in {"localhost", "127.0.0.1"}
    if parsed.scheme != "https" and not (
        allow_local_http and parsed.scheme == "http" and is_local
    ):
        raise ConfigurationError(f"{name} має використовувати HTTPS")
    return value


def get_image_storage_dir() -> Path:
    """Повертає шлях до каталогу сховища зображень (поза writable layer контейнера)."""
    env_dir = os.getenv("IMAGE_STORAGE_DIR", "").strip()
    if env_dir:
        return Path(env_dir).resolve()
    return (Path(tempfile.gettempdir()) / "baraholka-uploads").resolve()


@dataclass(frozen=True)
class EntraSettings:
    tenant_id: UUID
    client_id: str
    client_secret: str
    redirect_uri: str
    frontend_url: str
    session_cookie_secure: bool
    session_ttl_seconds: int = 8 * 60 * 60
    oidc_flow_ttl_seconds: int = 10 * 60

    @property
    def issuer(self) -> str:
        return f"https://login.microsoftonline.com/{self.tenant_id}/v2.0"

    @property
    def authority(self) -> str:
        return f"https://login.microsoftonline.com/{self.tenant_id}"

    @classmethod
    def from_env(cls) -> "EntraSettings":
        try:
            tenant_id = UUID(_required("MICROSOFT_TENANT_ID"))
        except ValueError as exc:
            raise ConfigurationError("MICROSOFT_TENANT_ID має бути UUID") from exc

        redirect_uri = _validate_url(
            _required("MICROSOFT_REDIRECT_URI"),
            "MICROSOFT_REDIRECT_URI",
            allow_local_http=True,
        )
        frontend_url = _validate_url(
            os.getenv("FRONTEND_URL", "http://localhost:5173").strip(),
            "FRONTEND_URL",
            allow_local_http=True,
        )
        secure_value = os.getenv("SESSION_COOKIE_SECURE")
        if secure_value is None:
            cookie_secure = redirect_uri.startswith("https://")
        elif secure_value.casefold() in {"1", "true", "yes"}:
            cookie_secure = True
        elif secure_value.casefold() in {"0", "false", "no"}:
            cookie_secure = False
        else:
            raise ConfigurationError("SESSION_COOKIE_SECURE має бути true або false")
        if redirect_uri.startswith("https://") and not cookie_secure:
            raise ConfigurationError(
                "HTTPS redirect URI вимагає SESSION_COOKIE_SECURE=true"
            )
        return cls(
            tenant_id=tenant_id,
            client_id=_required("MICROSOFT_CLIENT_ID"),
            client_secret=_required("MICROSOFT_CLIENT_SECRET"),
            redirect_uri=redirect_uri,
            frontend_url=frontend_url,
            session_cookie_secure=cookie_secure,
        )
