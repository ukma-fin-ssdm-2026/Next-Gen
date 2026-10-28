"""Модульні тести Favorite Service і репозиторію обраного без HTTP (FR-009)."""

from datetime import datetime, timezone
from uuid import uuid4

import pytest

from src.domain.exceptions import (
    FavoriteNotFoundError,
    ListingNotFoundError,
    ListingUnauthorizedError,
)
from src.domain.favorites import Favorite
from src.domain.listings import (
    SEED_LISTING_ID,
    SEED_OWNER_ID,
    WITHDRAWN_LISTING_ID,
    ListingStatus,
)
from src.repositories.favorites import InMemoryFavoriteRepository
from src.repositories.listings import InMemoryListingRepository
from src.services.favorites import FavoriteService
from src.services.listings import ListingService

BUYER_ID = uuid4()


@pytest.fixture
def listings() -> InMemoryListingRepository:
    return InMemoryListingRepository.with_seed()


@pytest.fixture
def favorites() -> InMemoryFavoriteRepository:
    return InMemoryFavoriteRepository()


@pytest.fixture
def service(
    favorites: InMemoryFavoriteRepository, listings: InMemoryListingRepository
) -> FavoriteService:
    return FavoriteService(favorites, listings)


def test_add_active_listing_appears_in_list(service: FavoriteService) -> None:
    """[TP-012] [FR-009]
    Додавання активного оголошення в обране з'являється у списку.
    """
    # Arrange: обране покупця порожнє
    # Act
    service.add(BUYER_ID, SEED_LISTING_ID)
    # Assert
    assert [item.id for item in service.list_for(BUYER_ID)] == [SEED_LISTING_ID]


def test_add_twice_does_not_duplicate(service: FavoriteService) -> None:
    """[TP-012] [FR-009] Повторне додавання не створює дублікатів."""
    first = service.add(BUYER_ID, SEED_LISTING_ID)
    second = service.add(BUYER_ID, SEED_LISTING_ID)
    assert second == first
    assert len(service.list_for(BUYER_ID)) == 1


def test_add_requires_actor(service: FavoriteService) -> None:
    """[TP-012] [FR-009] Додавання в обране вимагає авторизованого актора."""
    with pytest.raises(ListingUnauthorizedError):
        service.add(None, SEED_LISTING_ID)


@pytest.mark.parametrize("listing_id", [WITHDRAWN_LISTING_ID, uuid4()])
def test_add_rejects_withdrawn_or_unknown_listing(
    service: FavoriteService, favorites: InMemoryFavoriteRepository, listing_id
) -> None:
    """[TP-012] [FR-009] Відхилення додавання знятих або неіснуючих оголошень."""
    with pytest.raises(ListingNotFoundError):
        service.add(BUYER_ID, listing_id)
    assert favorites.list_by_user(BUYER_ID) == []


def test_favorites_are_private_per_user(service: FavoriteService) -> None:
    """[TP-013] [FR-009] Список обраного приватний для кожного користувача."""
    service.add(BUYER_ID, SEED_LISTING_ID)
    assert service.list_for(uuid4()) == []


def test_list_requires_actor(service: FavoriteService) -> None:
    """[TP-013] [FR-009] Перегляд обраного вимагає авторизованого актора."""
    with pytest.raises(ListingUnauthorizedError):
        service.list_for(None)


def test_remove_deletes_only_this_entry(service: FavoriteService) -> None:
    """[TP-014] [FR-009] Видалення з обраного видаляє лише обраний запис."""
    service.add(BUYER_ID, SEED_LISTING_ID)
    service.remove(BUYER_ID, SEED_LISTING_ID)
    assert service.list_for(BUYER_ID) == []


def test_remove_missing_entry_raises(service: FavoriteService) -> None:
    """[TP-014] [FR-009] Видалення відсутнього запису викликає FavoriteNotFoundError."""
    with pytest.raises(FavoriteNotFoundError):
        service.remove(BUYER_ID, SEED_LISTING_ID)


def test_listing_withdrawn_after_adding_is_hidden(
    service: FavoriteService, listings: InMemoryListingRepository
) -> None:
    """[TP-014] [FR-009] Зняте після додавання оголошення приховується з обраного."""
    service.add(BUYER_ID, SEED_LISTING_ID)
    listing = listings.get(SEED_LISTING_ID)
    listing.status = ListingStatus.WITHDRAWN
    listings.save(listing)
    assert service.list_for(BUYER_ID) == []


def test_withdrawing_listing_removes_it_from_all_favorites(
    service: FavoriteService,
    favorites: InMemoryFavoriteRepository,
    listings: InMemoryListingRepository,
) -> None:
    """[TP-014] [FR-009] Зняття оголошення власником очищає його з усіх списків."""
    # Arrange: два покупці зберегли те саме оголошення
    other_buyer = uuid4()
    service.add(BUYER_ID, SEED_LISTING_ID)
    service.add(other_buyer, SEED_LISTING_ID)
    listing_service = ListingService(listings, favorites=favorites)
    # Act: власник знімає оголошення з публікації
    listing_service.delete(SEED_LISTING_ID, SEED_OWNER_ID)
    # Assert: записів в обраному не лишилось, а не лише приховано
    assert favorites.list_by_user(BUYER_ID) == []
    assert favorites.list_by_user(other_buyer) == []


def test_list_orders_newest_added_first(
    favorites: InMemoryFavoriteRepository, listings: InMemoryListingRepository
) -> None:
    """[TP-013] [FR-009] Список обраного сортується від найновіших доданих."""
    second_listing = listings.get(SEED_LISTING_ID)
    newer = InMemoryListingRepository.with_seed().get(SEED_LISTING_ID)
    newer.id = uuid4()
    listings.add(newer)
    favorites.add(
        Favorite(
            BUYER_ID,
            second_listing.id,
            created_at=datetime(2026, 10, 1, tzinfo=timezone.utc),
        )
    )
    favorites.add(
        Favorite(
            BUYER_ID, newer.id, created_at=datetime(2026, 10, 2, tzinfo=timezone.utc)
        )
    )
    service = FavoriteService(favorites, listings)
    assert [item.id for item in service.list_for(BUYER_ID)] == [
        newer.id,
        second_listing.id,
    ]


def test_repository_delete_reports_missing_entry() -> None:
    """[TP-014] [FR-009] Репозиторій повертає False при видаленні відсутнього."""
    repo = InMemoryFavoriteRepository()
    assert repo.delete(BUYER_ID, SEED_LISTING_ID) is False
    assert repo.delete_by_listing(SEED_LISTING_ID) == 0
