"""Перевірка Entra claims і створення локальної ідентичності користувача."""

from dataclasses import dataclass
from datetime import datetime, timezone
from uuid import UUID

from src.domain.users import CurrentUser, User, UserRole
from src.repositories.users import UserRepository

UKMA_EMAIL_DOMAIN = "ukma.edu.ua"


class AuthenticationError(Exception):
    """Базова помилка перевірки ідентичності."""


class InvalidIdentityError(AuthenticationError):
    """Claims не відповідають конфігурації застосунку або політиці НаУКМА."""


class BlockedUserError(AuthenticationError):
    """Локальний профіль користувача заблоковано."""

    def __init__(self, message: str, user_id: UUID | None = None) -> None:
        super().__init__(message)
        self.user_id = user_id


class InvalidSessionError(AuthenticationError):
    """Сесія не вказує на наявного локального користувача."""


@dataclass(frozen=True)
class EntraAuthConfig:
    """Очікувані значення single-tenant реєстрації застосунку."""

    tenant_id: UUID
    issuer: str
    audience: str


@dataclass(frozen=True)
class VerifiedEntraClaims:
    """Claims токена після зовнішньої криптографічної перевірки підпису."""

    tenant_id: UUID
    object_id: UUID
    issuer: str
    audience: str
    expires_at: datetime
    email: str
    display_name: str


class AuthService:
    """Зв'язує перевірену Entra-ідентичність із локальним профілем."""

    def __init__(
        self,
        repository: UserRepository,
        config: EntraAuthConfig,
        admin_emails: frozenset[str] = frozenset(),
    ) -> None:
        self._repository = repository
        self._config = config
        self._admin_emails = admin_emails

    def authenticate_verified_claims(
        self,
        claims: VerifiedEntraClaims,
        now: datetime | None = None,
    ) -> CurrentUser:
        """Перевіряє claims, створює/оновлює User і повертає CurrentUser.

        Перевірка підпису JWT і nonce виконується OIDC-адаптером до виклику
        цього методу; сервіс не приймає claims без такої перевірки.
        """

        current_time = now or datetime.now(timezone.utc)
        normalized_email = self._validate_claims(claims, current_time)
        user = self._repository.get_by_entra_identity(
            claims.tenant_id, claims.object_id
        )
        if user is not None and user.is_blocked:
            raise BlockedUserError(
                "Обліковий запис користувача заблоковано", user.user_id
            )

        if user is None:
            user = User(
                tenant_id=claims.tenant_id,
                entra_object_id=claims.object_id,
                email=normalized_email,
                display_name=claims.display_name.strip(),
            )
        else:
            user.email = normalized_email
            if not user.display_name_customized:
                user.display_name = claims.display_name.strip()

        # Список ADMIN_EMAILS — єдине джерело ролі: адреса зі списку отримує
        # ADMIN, відсутня в ньому повертається до USER при наступному вході.
        user.role = (
            UserRole.ADMIN if normalized_email in self._admin_emails else UserRole.USER
        )
        saved = self._repository.save(user)
        return CurrentUser(
            user_id=saved.user_id,
            tenant_id=saved.tenant_id,
            entra_object_id=saved.entra_object_id,
            email=saved.email,
            display_name=saved.display_name,
            role=saved.role,
            avatar_url=saved.avatar_url,
            contact=saved.contact,
        )

    def get_current_user(self, user_id: UUID) -> CurrentUser:
        """Повторно читає локальний профіль для кожного захищеного запиту."""
        user = self._repository.get_by_id(user_id)
        if user is None:
            raise InvalidSessionError("Сесія користувача недійсна")
        if user.is_blocked:
            raise BlockedUserError(
                "Обліковий запис користувача заблоковано", user.user_id
            )
        return CurrentUser(
            user_id=user.user_id,
            tenant_id=user.tenant_id,
            entra_object_id=user.entra_object_id,
            email=user.email,
            display_name=user.display_name,
            role=user.role,
            avatar_url=user.avatar_url,
            contact=user.contact,
        )

    def _validate_claims(
        self, claims: VerifiedEntraClaims, current_time: datetime
    ) -> str:
        if claims.tenant_id != self._config.tenant_id:
            raise InvalidIdentityError("Неочікуваний Microsoft Entra tenant")
        if claims.issuer != self._config.issuer:
            raise InvalidIdentityError("Неочікуваний issuer токена")
        if claims.audience != self._config.audience:
            raise InvalidIdentityError("Токен видано для іншого застосунку")
        if claims.expires_at.tzinfo is None or claims.expires_at <= current_time:
            raise InvalidIdentityError("Термін дії токена завершився")
        return self._normalize_ukma_email(claims.email)

    @staticmethod
    def _normalize_ukma_email(email: str) -> str:
        normalized = email.strip().casefold()
        local_part, separator, domain = normalized.partition("@")
        if not local_part or separator != "@" or domain != UKMA_EMAIL_DOMAIN:
            raise InvalidIdentityError("Потрібна підтверджена адреса @ukma.edu.ua")
        return normalized
