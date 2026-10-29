"""Модульні тести UserModerationService (FR-013, SEC-001)."""

from uuid import uuid4

import pytest

from src.domain.exceptions import (
    InvalidModerationReasonError,
    InvalidUserModerationError,
    ListingUnauthorizedError,
    ModerationForbiddenError,
    UserNotFoundError,
)
from src.domain.moderation import ModerationActionType
from src.domain.users import CurrentUser, User, UserRole
from src.repositories.moderation import InMemoryModerationActionRepository
from src.repositories.users import InMemoryUserRepository
from src.services.auth_sessions import InMemoryAuthSessionStore
from src.services.user_moderation import UserModerationService

REASON = "Систематичні порушення правил"


def _user(role: UserRole = UserRole.USER) -> User:
    return User(
        tenant_id=uuid4(),
        entra_object_id=uuid4(),
        email=f"u-{uuid4().hex[:6]}@ukma.edu.ua",
        display_name="U",
        role=role,
    )


def _current(user: User) -> CurrentUser:
    return CurrentUser(
        user_id=user.user_id,
        tenant_id=user.tenant_id,
        entra_object_id=user.entra_object_id,
        email=user.email,
        display_name=user.display_name,
        role=user.role,
    )


@pytest.fixture
def env():
    admin, target = _user(UserRole.ADMIN), _user()
    users = InMemoryUserRepository([admin, target])
    actions = InMemoryModerationActionRepository()
    sessions = InMemoryAuthSessionStore()
    service = UserModerationService(users, actions, sessions)
    return service, users, actions, sessions, admin, target


def test_admin_blocks_user_revokes_sessions_and_audits(env) -> None:
    """[TP-026] [FR-013] [SEC-001]
    Блокування ставить is_blocked, відкликає всі сесії й пише запис аудиту.
    """
    service, users, actions, sessions, admin, target = env
    token1, token2 = sessions.create(target.user_id), sessions.create(target.user_id)
    other = sessions.create(admin.user_id)
    action = service.block_user(_current(admin), target.user_id, f"  {REASON} ")
    assert users.get_by_id(target.user_id).is_blocked is True
    assert sessions.resolve(token1) is None and sessions.resolve(token2) is None
    assert sessions.resolve(other) == admin.user_id
    assert action.action_type == ModerationActionType.BLOCK_USER
    assert action.target_user_id == target.user_id and action.listing_id is None
    assert action.reason == REASON
    assert actions.list_by_user(target.user_id) == [action]


def test_unblock_restores_access_and_audits(env) -> None:
    """[TP-026] [FR-013] Розблокування знімає is_blocked і пише запис аудиту."""
    service, users, actions, _, admin, target = env
    service.block_user(_current(admin), target.user_id, REASON)
    action = service.unblock_user(_current(admin), target.user_id, REASON)
    assert users.get_by_id(target.user_id).is_blocked is False
    assert action.action_type == ModerationActionType.UNBLOCK_USER
    assert len(actions.list_by_user(target.user_id)) == 2


def test_non_admin_and_anonymous_rejected_without_change(env) -> None:
    """[TP-026] [FR-013] [SEC-001] Не-ADMIN — Forbidden, без актора — Unauthorized."""
    service, users, actions, _, _, target = env
    with pytest.raises(ModerationForbiddenError):
        service.block_user(_current(_user()), target.user_id, REASON)
    with pytest.raises(ListingUnauthorizedError):
        service.block_user(None, target.user_id, REASON)
    assert users.get_by_id(target.user_id).is_blocked is False
    assert actions.list_by_user(target.user_id) == []


@pytest.mark.parametrize("reason", ["", "    ", "abcd", "x" * 501])
def test_reason_bounds_enforced(env, reason: str) -> None:
    """[TP-026] [FR-013] Причина поза межами 5–500 символів відхиляється."""
    service, users, _, _, admin, target = env
    with pytest.raises(InvalidModerationReasonError):
        service.block_user(_current(admin), target.user_id, reason)
    assert users.get_by_id(target.user_id).is_blocked is False


def test_invalid_targets_and_states(env) -> None:
    """[TP-026] [FR-013] Невідомий, сам себе, адміністратор, повторна дія."""
    service, _, _, _, admin, target = env
    with pytest.raises(UserNotFoundError):
        service.block_user(_current(admin), uuid4(), REASON)
    with pytest.raises(InvalidUserModerationError):
        service.block_user(_current(admin), admin.user_id, REASON)
    with pytest.raises(InvalidUserModerationError):
        service.unblock_user(_current(admin), target.user_id, REASON)
    service.block_user(_current(admin), target.user_id, REASON)
    with pytest.raises(InvalidUserModerationError):
        service.block_user(_current(admin), target.user_id, REASON)
    other_admin = _user(UserRole.ADMIN)
    service._users.save(other_admin)
    with pytest.raises(InvalidUserModerationError):
        service.block_user(_current(admin), other_admin.user_id, REASON)


def test_failed_audit_rolls_back_block(env) -> None:
    """[TP-026] [FR-013] Збій запису аудиту відкочує блокування й не відкликає сесії."""
    service, users, actions, sessions, admin, target = env
    token = sessions.create(target.user_id)

    def boom(_action):
        raise RuntimeError("audit down")

    actions.add = boom
    with pytest.raises(RuntimeError):
        service.block_user(_current(admin), target.user_id, REASON)
    assert users.get_by_id(target.user_id).is_blocked is False
    assert sessions.resolve(token) == target.user_id


def test_block_and_unblock_by_email_is_case_insensitive(env) -> None:
    """[TP-026] [FR-013] Блокування й розблокування за email без урахування регістру."""
    service, users, actions, _, admin, target = env
    action = service.block_user_by_email(
        _current(admin), f"  {target.email.upper()} ", REASON
    )
    assert users.get_by_id(target.user_id).is_blocked is True
    assert action.target_user_id == target.user_id
    service.unblock_user_by_email(_current(admin), target.email, REASON)
    assert users.get_by_id(target.user_id).is_blocked is False
    assert len(actions.list_by_user(target.user_id)) == 2


def test_by_email_checks_rights_before_lookup(env) -> None:
    """[TP-026] [FR-013] [SEC-001]
    Не-адміністратор отримує Forbidden і для відомої, і для невідомої адреси,
    тобто не може з'ясувати, чи є адреса в системі.
    """
    service, _, _, _, _, target = env
    plain = _current(_user())
    for email in (target.email, "nobody@ukma.edu.ua"):
        with pytest.raises(ModerationForbiddenError):
            service.block_user_by_email(plain, email, REASON)
    with pytest.raises(ListingUnauthorizedError):
        service.block_user_by_email(None, target.email, REASON)


def test_by_email_unknown_address_is_not_found(env) -> None:
    """[TP-026] [FR-013] Невідома адреса — UserNotFoundError без запису аудиту."""
    service, _, actions, _, admin, _ = env
    with pytest.raises(UserNotFoundError):
        service.block_user_by_email(_current(admin), "nobody@ukma.edu.ua", REASON)
    assert actions._items == []
