"""Модульні тести ProfileService (FR-014, US-009)."""

from uuid import uuid4

import pytest

from src.domain.exceptions import InvalidProfileError, ProfileNotFoundError
from src.domain.users import CurrentUser, User
from src.repositories.image_storage import InMemoryImageStorage
from src.repositories.users import InMemoryUserRepository
from src.services.auth import AuthService, EntraAuthConfig, VerifiedEntraClaims
from src.services.profile import ProfileService
from tests.conftest import make_dummy_jpeg


def _setup() -> (
    tuple[ProfileService, InMemoryUserRepository, InMemoryImageStorage, User]
):
    users = InMemoryUserRepository()
    images = InMemoryImageStorage()
    user = users.save(
        User(
            tenant_id=uuid4(),
            entra_object_id=uuid4(),
            email="a@ukma.edu.ua",
            display_name="Entra Name",
        )
    )
    return ProfileService(users, images), users, images, user


def _actor(user: User) -> CurrentUser:
    return CurrentUser(
        user_id=user.user_id,
        tenant_id=user.tenant_id,
        entra_object_id=user.entra_object_id,
        email=user.email,
        display_name=user.display_name,
        role=user.role,
    )


def test_update_name_and_contact_persists() -> None:
    """[TP-024] [US-009] [FR-014] Ім'я та контакти зберігаються й обрізаються."""
    service, users, _, user = _setup()
    result = service.update(
        _actor(user),
        display_name="  Іван  ",
        update_name=True,
        contact=" Тел.: +380 ",
        update_contact=True,
    )
    assert result.display_name == "Іван"
    assert result.contact == "Тел.: +380"
    assert users.get_by_id(user.user_id).display_name_customized is True


@pytest.mark.parametrize("name", ["", "   ", "x" * 101])
def test_invalid_name_rejected(name: str) -> None:
    """[TP-024] [FR-014] Порожнє або надто довге ім'я відхиляється."""
    service, _, _, user = _setup()
    with pytest.raises(InvalidProfileError):
        service.update(_actor(user), display_name=name, update_name=True)


def test_contact_too_long_rejected_and_empty_clears() -> None:
    """[TP-024] [FR-014] Надто довгі контакти відхиляються, порожні очищають."""
    service, _, _, user = _setup()
    with pytest.raises(InvalidProfileError):
        service.update(_actor(user), contact="x" * 301, update_contact=True)
    service.update(_actor(user), contact="abc", update_contact=True)
    cleared = service.update(_actor(user), contact="", update_contact=True)
    assert cleared.contact is None


def test_unspecified_fields_unchanged() -> None:
    """[TP-024] [FR-014] Непередані поля не змінюються."""
    service, _, _, user = _setup()
    service.update(_actor(user), contact="abc", update_contact=True)
    result = service.update(_actor(user), display_name="Нове", update_name=True)
    assert result.contact == "abc"


def test_avatar_set_replace_remove() -> None:
    """[TP-024] [FR-014] [TM-03] Аватарка встановлюється, замінюється й видаляється."""
    service, _, images, user = _setup()
    first = service.set_avatar(_actor(user), make_dummy_jpeg())
    assert first.avatar_url and first.avatar_url.startswith("/uploads/")
    key1 = first.avatar_url.rsplit("/", 1)[1]
    second = service.set_avatar(_actor(user), make_dummy_jpeg(color=(1, 2, 3)))
    assert second.avatar_url != first.avatar_url
    with pytest.raises(Exception):
        images.read_image(key1)
    removed = service.remove_avatar(_actor(user))
    assert removed.avatar_url is None
    assert service.remove_avatar(_actor(user)).avatar_url is None


def test_invalid_avatar_bytes_rejected() -> None:
    """[TP-024] [FR-014] [TM-03] Не-зображення як аватарка відхиляється."""
    service, _, _, user = _setup()
    with pytest.raises(InvalidProfileError):
        service.set_avatar(_actor(user), b"not an image")


def test_unknown_user_not_found() -> None:
    """[TP-024] [FR-014] Профіль неіснуючого користувача — ProfileNotFoundError."""
    service, _, _, user = _setup()
    with pytest.raises(ProfileNotFoundError):
        service.get_public(uuid4())
    ghost = _actor(user)
    object.__setattr__(ghost, "user_id", uuid4())
    with pytest.raises(ProfileNotFoundError):
        service.update(ghost, contact="x", update_contact=True)


def test_login_keeps_customized_name() -> None:
    """[TP-024] [FR-014] Повторний вхід не перезаписує змінене користувачем ім'я."""
    from datetime import datetime, timedelta, timezone

    users = InMemoryUserRepository()
    tenant = uuid4()
    auth = AuthService(
        users, EntraAuthConfig(tenant_id=tenant, issuer="iss", audience="aud")
    )
    claims = VerifiedEntraClaims(
        tenant_id=tenant,
        object_id=uuid4(),
        issuer="iss",
        audience="aud",
        expires_at=datetime.now(timezone.utc) + timedelta(hours=1),
        email="b@ukma.edu.ua",
        display_name="Entra",
    )
    current = auth.authenticate_verified_claims(claims)
    ProfileService(users, InMemoryImageStorage()).update(
        current, display_name="Мій нік", update_name=True
    )
    again = auth.authenticate_verified_claims(claims)
    assert again.display_name == "Мій нік"
