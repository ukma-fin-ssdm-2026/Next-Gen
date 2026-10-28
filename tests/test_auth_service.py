"""Модульні тести першого зрізу Microsoft Entra ID автентифікації."""

from dataclasses import replace
from datetime import datetime, timedelta, timezone
from uuid import UUID, uuid4

import pytest

from src.domain.users import User, UserRole
from src.repositories.users import InMemoryUserRepository
from src.services.auth import (
    AuthService,
    BlockedUserError,
    EntraAuthConfig,
    InvalidIdentityError,
    VerifiedEntraClaims,
)

TENANT_ID = UUID("11111111-1111-1111-1111-111111111111")
OBJECT_ID = UUID("22222222-2222-2222-2222-222222222222")
CLIENT_ID = "baraholka-client-id"
ISSUER = f"https://login.microsoftonline.com/{TENANT_ID}/v2.0"
NOW = datetime(2026, 10, 26, 12, 0, tzinfo=timezone.utc)


@pytest.fixture
def auth_config() -> EntraAuthConfig:
    return EntraAuthConfig(
        tenant_id=TENANT_ID,
        issuer=ISSUER,
        audience=CLIENT_ID,
    )


@pytest.fixture
def valid_claims() -> VerifiedEntraClaims:
    return VerifiedEntraClaims(
        tenant_id=TENANT_ID,
        object_id=OBJECT_ID,
        issuer=ISSUER,
        audience=CLIENT_ID,
        expires_at=NOW + timedelta(minutes=30),
        email="  Student@UKMA.EDU.UA ",
        display_name="  Студент НаУКМА  ",
    )


def test_valid_claims_create_local_user_and_current_user(
    auth_config: EntraAuthConfig,
    valid_claims: VerifiedEntraClaims,
) -> None:
    """[TP-AUTH-01] [FR-001] [SEC-001]
    Створення локального та CurrentUser за валідними claims.
    """
    repository = InMemoryUserRepository()
    service = AuthService(repository, auth_config)

    current_user = service.authenticate_verified_claims(valid_claims, now=NOW)
    saved = repository.get_by_entra_identity(TENANT_ID, OBJECT_ID)

    assert saved is not None
    assert current_user.user_id == saved.user_id
    assert current_user.email == "student@ukma.edu.ua"
    assert current_user.role == UserRole.USER
    assert saved.display_name == "Студент НаУКМА"


def test_existing_entra_identity_updates_profile_without_changing_local_id(
    auth_config: EntraAuthConfig,
    valid_claims: VerifiedEntraClaims,
) -> None:
    """[TP-AUTH-01] [FR-001] [SEC-001]
    Оновлення профілю існуючого користувача без зміни user_id.
    """
    existing = User(
        tenant_id=TENANT_ID,
        entra_object_id=OBJECT_ID,
        email="old@ukma.edu.ua",
        display_name="Старе ім'я",
        role=UserRole.ADMIN,
    )
    repository = InMemoryUserRepository([existing])
    service = AuthService(repository, auth_config)

    current_user = service.authenticate_verified_claims(valid_claims, now=NOW)

    assert current_user.user_id == existing.user_id
    assert current_user.role == UserRole.ADMIN
    assert existing.email == "student@ukma.edu.ua"
    assert existing.display_name == "Студент НаУКМА"


@pytest.mark.parametrize(
    ("changed_claims", "expected_message"),
    [
        (
            {"tenant_id": uuid4()},
            "Неочікуваний Microsoft Entra tenant",
        ),
        ({"issuer": "https://issuer.example"}, "Неочікуваний issuer токена"),
        ({"audience": "other-client"}, "Токен видано для іншого застосунку"),
        ({"expires_at": NOW}, "Термін дії токена завершився"),
        (
            {"email": "student@gmail.com"},
            "Потрібна підтверджена адреса @ukma.edu.ua",
        ),
        (
            {"email": "@ukma.edu.ua"},
            "Потрібна підтверджена адреса @ukma.edu.ua",
        ),
    ],
    ids=[
        "wrong-tenant",
        "wrong-issuer",
        "wrong-audience",
        "expired-token",
        "foreign-email-domain",
        "empty-email-local-part",
    ],
)
def test_nfr_sec_01_invalid_claims_are_rejected(
    auth_config: EntraAuthConfig,
    valid_claims: VerifiedEntraClaims,
    changed_claims: dict[str, object],
    expected_message: str,
) -> None:
    """[TP-AUTH-02] [FR-001] [SEC-001]
    Відхилення невалідних claims (NFR security перевірка).
    """
    repository = InMemoryUserRepository()
    service = AuthService(repository, auth_config)
    invalid_claims = replace(valid_claims, **changed_claims)

    with pytest.raises(InvalidIdentityError) as exc_info:
        service.authenticate_verified_claims(invalid_claims, now=NOW)

    assert str(exc_info.value) == expected_message
    assert (
        repository.get_by_entra_identity(
            invalid_claims.tenant_id,
            invalid_claims.object_id,
        )
        is None
    )


def test_blocked_local_user_is_rejected_without_profile_update(
    auth_config: EntraAuthConfig,
    valid_claims: VerifiedEntraClaims,
) -> None:
    """[TP-AUTH-01] [FR-001] [SEC-001]
    Відхилення заблокованого локального користувача (403).
    """
    blocked = User(
        tenant_id=TENANT_ID,
        entra_object_id=OBJECT_ID,
        email="blocked@ukma.edu.ua",
        display_name="Заблокований користувач",
        is_blocked=True,
    )
    repository = InMemoryUserRepository([blocked])
    service = AuthService(repository, auth_config)

    with pytest.raises(BlockedUserError) as exc_info:
        service.authenticate_verified_claims(valid_claims, now=NOW)

    assert str(exc_info.value) == "Обліковий запис користувача заблоковано"
    assert blocked.email == "blocked@ukma.edu.ua"
