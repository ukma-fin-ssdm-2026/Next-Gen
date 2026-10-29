"""Модульні тести Moderation Service (FR-011). Підхід AAA."""

import threading
import time
from dataclasses import FrozenInstanceError
from uuid import uuid4

import pytest

from src.domain.exceptions import (
    InvalidModerationReasonError,
    ListingNotFoundError,
    ListingUnauthorizedError,
    ModerationForbiddenError,
)
from src.domain.favorites import Favorite
from src.domain.listings import ListingStatus, SEED_LISTING_ID, WITHDRAWN_LISTING_ID
from src.domain.moderation import (
    MODERATION_REASON_MAX_LENGTH,
    MODERATION_REASON_MIN_LENGTH,
    ModerationAction,
    ModerationActionType,
)
from src.domain.users import CurrentUser, UserRole
from src.repositories.favorites import InMemoryFavoriteRepository
from src.repositories.listings import InMemoryListingRepository
from src.repositories.moderation import InMemoryModerationActionRepository
from src.services.moderation import ModerationService

REASON = "Заборонений товар"


def make_user(role: UserRole) -> CurrentUser:
    return CurrentUser(
        user_id=uuid4(),
        tenant_id=uuid4(),
        entra_object_id=uuid4(),
        email="someone@ukma.edu.ua",
        display_name="Someone",
        role=role,
    )


ADMIN = make_user(UserRole.ADMIN)
STUDENT = make_user(UserRole.USER)


class FailingActionRepository(InMemoryModerationActionRepository):
    """Імітує збій запису аудиту після зміни статусу й очищення обраного."""

    def add(self, action: ModerationAction) -> ModerationAction:
        raise RuntimeError("audit storage unavailable")


class FailingListingRepository(InMemoryListingRepository):
    """Імітує збій збереження статусу оголошення (першої зміни стану)."""

    def __init__(self) -> None:
        super().__init__(InMemoryListingRepository.with_seed().list_all())
        self.fail = True

    def save(self, listing):
        if self.fail and listing.status == ListingStatus.WITHDRAWN:
            raise RuntimeError("listing storage unavailable")
        return super().save(listing)


@pytest.fixture
def listings() -> InMemoryListingRepository:
    return InMemoryListingRepository.with_seed()


@pytest.fixture
def favorites() -> InMemoryFavoriteRepository:
    return InMemoryFavoriteRepository()


@pytest.fixture
def actions() -> InMemoryModerationActionRepository:
    return InMemoryModerationActionRepository()


@pytest.fixture
def service(listings, favorites, actions) -> ModerationService:
    return ModerationService(listings, favorites, actions)


def test_admin_withdraws_active_listing_and_records_action(
    service, listings, favorites, actions
) -> None:
    """[TP-020] [FR-011]
    ADMIN знімає активне оголошення: WITHDRAWN, обране очищене, аудит збережено.
    """
    # Arrange
    buyer_id = uuid4()
    favorites.add(Favorite(user_id=buyer_id, listing_id=SEED_LISTING_ID))
    # Act
    action = service.withdraw_listing(ADMIN, SEED_LISTING_ID, f"  {REASON}  ")
    # Assert
    stored = listings.get(SEED_LISTING_ID)
    assert stored is not None, "оголошення не видаляється фізично"
    assert stored.status == ListingStatus.WITHDRAWN
    assert favorites.list_by_user(buyer_id) == []
    assert actions.list_by_listing(SEED_LISTING_ID) == [action]
    assert action.moderator_id == ADMIN.user_id
    assert action.action_type == ModerationActionType.WITHDRAW_LISTING
    assert action.reason == REASON


def test_non_admin_is_forbidden_and_state_unchanged(service, listings, actions) -> None:
    """[TP-020] [FR-011] [SEC-001] Користувач без ролі ADMIN отримує відмову."""
    with pytest.raises(ModerationForbiddenError):
        service.withdraw_listing(STUDENT, SEED_LISTING_ID, REASON)
    assert listings.get(SEED_LISTING_ID).status == ListingStatus.ACTIVE
    assert actions.list_by_listing(SEED_LISTING_ID) == []


def test_missing_moderator_is_unauthorized(service) -> None:
    """[TP-020] [FR-011] Без ідентичності модерація неможлива."""
    with pytest.raises(ListingUnauthorizedError):
        service.withdraw_listing(None, SEED_LISTING_ID, REASON)


@pytest.mark.parametrize(
    "reason",
    ["", "   ", "x" * (MODERATION_REASON_MIN_LENGTH - 1)],
    ids=["empty", "whitespace", "below-min"],
)
def test_too_short_reason_is_rejected(service, listings, reason: str) -> None:
    """[TP-020] [FR-011] Порожня або закоротка причина відхиляється."""
    with pytest.raises(InvalidModerationReasonError):
        service.withdraw_listing(ADMIN, SEED_LISTING_ID, reason)
    assert listings.get(SEED_LISTING_ID).status == ListingStatus.ACTIVE


def test_too_long_reason_is_rejected(service) -> None:
    """[TP-020] [FR-011] Причина довша за максимум відхиляється."""
    with pytest.raises(InvalidModerationReasonError):
        service.withdraw_listing(
            ADMIN, SEED_LISTING_ID, "x" * (MODERATION_REASON_MAX_LENGTH + 1)
        )


@pytest.mark.parametrize(
    "length",
    [MODERATION_REASON_MIN_LENGTH, MODERATION_REASON_MAX_LENGTH],
    ids=["min", "max"],
)
def test_reason_length_boundaries_are_accepted(listings, length: int) -> None:
    """[TP-020] [FR-011] Причина рівно на межах довжини приймається."""
    service = ModerationService(
        listings, InMemoryFavoriteRepository(), InMemoryModerationActionRepository()
    )
    action = service.withdraw_listing(ADMIN, SEED_LISTING_ID, "x" * length)
    assert len(action.reason) == length


def test_unknown_listing_is_not_found(service) -> None:
    """[TP-020] [FR-011] Неіснуюче оголошення дає ListingNotFoundError."""
    with pytest.raises(ListingNotFoundError):
        service.withdraw_listing(ADMIN, uuid4(), REASON)


def test_already_withdrawn_listing_is_not_found(service, actions) -> None:
    """[TP-020] [FR-011] Повторне зняття не створює другого запису аудиту."""
    with pytest.raises(ListingNotFoundError):
        service.withdraw_listing(ADMIN, WITHDRAWN_LISTING_ID, REASON)
    assert actions.list_by_listing(WITHDRAWN_LISTING_ID) == []


def test_audit_failure_rolls_back_whole_operation(listings, favorites) -> None:
    """[TP-020] [FR-011]
    Збій запису аудиту відкочує статус і обране: часткового стану немає.
    """
    # Arrange
    buyer_id = uuid4()
    favorites.add(Favorite(user_id=buyer_id, listing_id=SEED_LISTING_ID))
    service = ModerationService(listings, favorites, FailingActionRepository())
    # Act
    with pytest.raises(RuntimeError):
        service.withdraw_listing(ADMIN, SEED_LISTING_ID, REASON)
    # Assert
    assert listings.get(SEED_LISTING_ID).status == ListingStatus.ACTIVE
    assert [f.listing_id for f in favorites.list_by_user(buyer_id)] == [SEED_LISTING_ID]


def test_listing_save_failure_leaves_no_audit_record(favorites, actions) -> None:
    """[TP-020] [FR-011] Збій зміни статусу не лишає аудиту й не чіпає обране."""
    listings = FailingListingRepository()
    buyer_id = uuid4()
    favorites.add(Favorite(user_id=buyer_id, listing_id=SEED_LISTING_ID))
    service = ModerationService(listings, favorites, actions)

    with pytest.raises(RuntimeError):
        service.withdraw_listing(ADMIN, SEED_LISTING_ID, REASON)

    assert listings.get(SEED_LISTING_ID).status == ListingStatus.ACTIVE
    assert actions.list_by_listing(SEED_LISTING_ID) == []
    assert len(favorites.list_by_user(buyer_id)) == 1


def test_moderation_action_is_immutable(service) -> None:
    """[TP-020] [FR-011] Запис модерації незмінний після створення."""
    action = service.withdraw_listing(ADMIN, SEED_LISTING_ID, REASON)
    with pytest.raises(FrozenInstanceError):
        action.reason = "інша причина"


class SlowListingRepository(InMemoryListingRepository):
    """Розширює вікно гонки: після читання оголошення потік «думає» 50 мс."""

    def get(self, listing_id):
        listing = super().get(listing_id)
        time.sleep(0.05)
        return listing


def test_concurrent_withdrawals_create_single_audit_record(favorites, actions) -> None:
    """[TP-020] [FR-011]
    Два адміністратори одночасно знімають одне оголошення: успішний лише один,
    у журналі рівно один запис, другий отримує ListingNotFoundError.
    """
    # Arrange
    listings = SlowListingRepository(InMemoryListingRepository.with_seed().list_all())
    service = ModerationService(listings, favorites, actions)
    admins = [make_user(UserRole.ADMIN), make_user(UserRole.ADMIN)]
    start = threading.Barrier(len(admins))
    outcomes: list[str] = []

    def withdraw(admin: CurrentUser) -> None:
        start.wait()
        try:
            service.withdraw_listing(admin, SEED_LISTING_ID, REASON)
            outcomes.append("ok")
        except ListingNotFoundError:
            outcomes.append("not_found")

    # Act
    threads = [threading.Thread(target=withdraw, args=(a,)) for a in admins]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join(timeout=5)

    # Assert
    assert sorted(outcomes) == ["not_found", "ok"]
    assert len(actions.list_by_listing(SEED_LISTING_ID)) == 1
