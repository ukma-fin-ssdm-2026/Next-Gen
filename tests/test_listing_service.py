"""Модульні тести Listing Service без HTTP."""

from datetime import datetime, timezone
from unittest.mock import Mock
from uuid import uuid4

import pytest

from src.domain.exceptions import (
    InvalidListingImageError,
    InvalidPriceRangeError,
    ListingForbiddenError,
    ListingNotFoundError,
    ListingUnauthorizedError,
)
from src.domain.listings import (
    SEED_CATEGORY_ID,
    SEED_LISTING_ID,
    SEED_OWNER_ID,
    WITHDRAWN_LISTING_ID,
    Listing,
    ListingCondition,
    ListingSortOrder,
)
from src.repositories.image_storage import InMemoryImageStorage
from src.repositories.listings import InMemoryListingRepository, ListingRepository
from src.services.listings import ListingService


def test_public_catalog_hides_withdrawn(listing_service: ListingService) -> None:
    items = listing_service.list_public()
    ids = {item.id for item in items}
    assert SEED_LISTING_ID in ids
    assert WITHDRAWN_LISTING_ID not in ids


def test_search_by_title(listing_service: ListingService) -> None:
    items = listing_service.list_public(query="худі")
    assert len(items) == 1
    assert items[0].id == SEED_LISTING_ID


def test_update_requires_owner(listing_service: ListingService) -> None:
    with pytest.raises(ListingForbiddenError) as exc_info:
        listing_service.update(
            SEED_LISTING_ID,
            actor_id=uuid4(),
            title="Спроба змінити чуже оголошення",
        )
    assert str(exc_info.value) == "Немає прав змінювати чуже оголошення"


def test_create_requires_actor(listing_service: ListingService) -> None:
    with pytest.raises(ListingUnauthorizedError) as exc_info:
        listing_service.create(
            actor_id=None,
            title="Конспект з алгебри",
            description="Друкований конспект, майже не користувався.",
            price=80.0,
            category_id=SEED_LISTING_ID,
            contact="@someone",
        )
    assert str(exc_info.value) == "Потрібна ідентифікація користувача"


def test_owner_can_update_title(listing_service: ListingService) -> None:
    updated = listing_service.update(
        SEED_LISTING_ID,
        actor_id=SEED_OWNER_ID,
        title="Худі НаУКМА, розмір M",
    )
    assert updated.title == "Худі НаУКМА, розмір M"
    assert updated.user_id == SEED_OWNER_ID


def test_owner_can_update_all_editable_fields(
    listing_service: ListingService,
) -> None:
    original = listing_service.get_public(SEED_LISTING_ID)
    previous_updated_at = original.updated_at

    updated = listing_service.update(
        SEED_LISTING_ID,
        actor_id=SEED_OWNER_ID,
        title="Оновлене худі",
        description="Оновлений опис оголошення.",
        price=175.0,
        contact="@updated_contact",
    )

    assert updated.title == "Оновлене худі"
    assert updated.description == "Оновлений опис оголошення."
    assert updated.price == 175.0
    assert updated.contact == "@updated_contact"
    assert updated.updated_at > previous_updated_at


def test_delete_marks_withdrawn_and_preserves_data(
    listing_service: ListingService,
) -> None:
    previous_updated_at = listing_service.get_public(SEED_LISTING_ID).updated_at
    deleted = listing_service.delete(SEED_LISTING_ID, actor_id=SEED_OWNER_ID)
    assert deleted.status.value == "WITHDRAWN"
    assert deleted.updated_at > previous_updated_at
    items = listing_service.list_public()
    assert SEED_LISTING_ID not in {item.id for item in items}
    with pytest.raises(ListingNotFoundError) as exc_info:
        listing_service.get_public(SEED_LISTING_ID)
    assert str(exc_info.value) == "Оголошення не знайдено"


def test_get_public_reports_missing_listing(listing_service: ListingService) -> None:
    with pytest.raises(ListingNotFoundError) as exc_info:
        listing_service.get_public(uuid4())
    assert str(exc_info.value) == "Оголошення не знайдено"


def test_filter_by_price_range(listing_service: ListingService) -> None:
    matched = listing_service.list_public(min_price=100.0, max_price=200.0)
    assert len(matched) == 1
    assert matched[0].id == SEED_LISTING_ID

    empty_high = listing_service.list_public(min_price=200.0)
    assert len(empty_high) == 0

    empty_low = listing_service.list_public(max_price=100.0)
    assert len(empty_low) == 0

    exact_boundary = listing_service.list_public(min_price=150.0, max_price=150.0)
    assert [item.id for item in exact_boundary] == [SEED_LISTING_ID]


def test_list_public_rejects_inverted_price_range(
    listing_service: ListingService,
) -> None:
    """Регресійний тест: запит з min_price > max_price відхиляється помилкою."""
    with pytest.raises(InvalidPriceRangeError) as exc_info:
        listing_service.list_public(min_price=200.0, max_price=100.0)
    assert (
        str(exc_info.value)
        == "min_price (200.0) не може перевищувати max_price (100.0)"
    )


def test_public_catalog_filters_by_category_and_searches_description() -> None:
    target_category = uuid4()
    title_match = Listing(
        title="Синій рюкзак",
        description="Без дефектів, майже новий.",
        price=500.0,
        category_id=target_category,
        contact="@title_match",
        user_id=SEED_OWNER_ID,
    )
    description_match = Listing(
        title="Портфель",
        description="Зручний синій аксесуар для навчання.",
        price=400.0,
        category_id=target_category,
        contact="@description_match",
        user_id=SEED_OWNER_ID,
    )
    other_category = Listing(
        title="Синій пенал",
        description="Канцелярія.",
        price=100.0,
        category_id=uuid4(),
        contact="@other_category",
        user_id=SEED_OWNER_ID,
    )
    service = ListingService(
        InMemoryListingRepository([title_match, description_match, other_category])
    )

    items = service.list_public(category_id=target_category, query="синій")

    assert {item.id for item in items} == {title_match.id, description_match.id}


def test_public_catalog_uses_default_limit_of_ten() -> None:
    listings = [
        Listing(
            title=f"Оголошення {index}",
            description="Валідний опис тестового оголошення.",
            price=float(index),
            category_id=SEED_CATEGORY_ID,
            contact="@student",
            user_id=SEED_OWNER_ID,
        )
        for index in range(11)
    ]
    service = ListingService(InMemoryListingRepository(listings))

    assert len(service.list_public()) == 10


def test_public_catalog_can_sort_oldest_first() -> None:
    older = Listing(
        title="Старіше оголошення",
        description="Тестовий опис старішого оголошення.",
        price=100.0,
        category_id=SEED_CATEGORY_ID,
        contact="@older",
        user_id=SEED_OWNER_ID,
        created_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
    )
    newer = Listing(
        title="Нове оголошення",
        description="Тестовий опис нового оголошення.",
        price=200.0,
        category_id=SEED_CATEGORY_ID,
        contact="@newer",
        user_id=SEED_OWNER_ID,
        created_at=datetime(2026, 1, 2, tzinfo=timezone.utc),
    )
    service = ListingService(InMemoryListingRepository([newer, older]))

    items = service.list_public(sort_order=ListingSortOrder.OLDEST)

    assert [item.id for item in items] == [older.id, newer.id]


def test_create_delegates_to_repository_and_uses_actor_as_owner() -> None:
    repository = Mock(spec=ListingRepository)
    repository.add.side_effect = lambda listing: listing
    service = ListingService(repository)
    actor_id = uuid4()

    created = service.create(
        actor_id=actor_id,
        title="Лабораторний халат",
        description="Чистий лабораторний халат розміру M.",
        price=300.0,
        category_id=SEED_CATEGORY_ID,
        contact="@student",
    )

    assert created.user_id == actor_id
    assert created.status.value == "ACTIVE"
    repository.add.assert_called_once_with(created)


def test_list_owner_listings_returns_active_and_withdrawn_for_seller(
    listing_service: ListingService,
) -> None:
    foreign_owner = uuid4()
    listing_service.create(
        actor_id=foreign_owner,
        title="Чуже оголошення",
        description="Опис чужого оголошення для перевірки фільтрації власника.",
        price=90.0,
        category_id=SEED_CATEGORY_ID,
        contact="@foreign_seller",
    )

    history = listing_service.list_owner_listings(actor_id=SEED_OWNER_ID)
    history_ids = {item.id for item in history}
    statuses = {item.status.value for item in history}

    assert history_ids == {SEED_LISTING_ID, WITHDRAWN_LISTING_ID}
    assert statuses == {"ACTIVE", "WITHDRAWN"}


def test_list_owner_listings_requires_actor(
    listing_service: ListingService,
) -> None:
    with pytest.raises(ListingUnauthorizedError):
        listing_service.list_owner_listings(actor_id=None)


def test_create_and_update_with_images_and_condition() -> None:
    storage = InMemoryImageStorage()
    repository = InMemoryListingRepository.with_seed()
    service = ListingService(repository=repository, image_storage=storage)

    created = service.create(
        actor_id=SEED_OWNER_ID,
        title="Калькулятор Casio",
        description="Інженерний калькулятор у відмінному стані.",
        price=450.0,
        category_id=SEED_CATEGORY_ID,
        contact="@casio_seller",
        condition=ListingCondition.NEW,
        image_urls=[
            " https://baraholka.ukma.edu.ua/images/casio-1.jpg ",
            "/uploads/casio-2.jpg",
        ],
    )

    assert created.condition == ListingCondition.NEW
    assert len(created.images) == 2
    assert created.images[0].image_url == (
        "https://baraholka.ukma.edu.ua/images/casio-1.jpg"
    )
    assert created.images[0].display_order == 0
    assert created.images[1].display_order == 1
    assert len(storage.get_images(created.id)) == 2

    updated = service.update(
        created.id,
        actor_id=SEED_OWNER_ID,
        condition=ListingCondition.USED,
        image_urls=["https://baraholka.ukma.edu.ua/images/casio-updated.jpg"],
    )
    assert updated.condition == ListingCondition.USED
    assert len(updated.images) == 1
    assert updated.images[0].image_url == (
        "https://baraholka.ukma.edu.ua/images/casio-updated.jpg"
    )


@pytest.mark.parametrize(
    "invalid_urls",
    [
        [""],
        ["   "],
        ["ftp://invalid-scheme.example.com/photo.jpg"],
        ["https://baraholka.ukma.edu.ua/images/has space.jpg"],
        [f"https://baraholka.ukma.edu.ua/images/{idx}.jpg" for idx in range(11)],
    ],
)
def test_image_storage_rejects_invalid_urls_or_too_many_images(
    listing_service: ListingService,
    invalid_urls: list[str],
) -> None:
    with pytest.raises(InvalidListingImageError):
        listing_service.create(
            actor_id=SEED_OWNER_ID,
            title="Підручник з економіки",
            description="Підручник для першого курсу у гарному стані.",
            price=200.0,
            category_id=SEED_CATEGORY_ID,
            contact="@econ_student",
            image_urls=invalid_urls,
        )
