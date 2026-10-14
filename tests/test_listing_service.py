"""Модульні тести Listing Service без HTTP."""

from uuid import uuid4

import pytest

from src.domain.exceptions import ListingForbiddenError, ListingUnauthorizedError
from src.domain.listings import SEED_LISTING_ID, SEED_OWNER_ID, WITHDRAWN_LISTING_ID
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
    with pytest.raises(ListingForbiddenError):
        listing_service.update(
            SEED_LISTING_ID,
            actor_id=uuid4(),
            title="Спроба змінити чуже оголошення",
        )


def test_create_requires_actor(listing_service: ListingService) -> None:
    with pytest.raises(ListingUnauthorizedError):
        listing_service.create(
            actor_id=None,
            title="Конспект з алгебри",
            description="Друкований конспект, майже не користувався.",
            price=80.0,
            category_id=SEED_LISTING_ID,
            contact="@someone",
        )


def test_owner_can_update_title(listing_service: ListingService) -> None:
    updated = listing_service.update(
        SEED_LISTING_ID,
        actor_id=SEED_OWNER_ID,
        title="Худі НаУКМА, розмір M",
    )
    assert updated.title == "Худі НаУКМА, розмір M"
    assert updated.user_id == SEED_OWNER_ID
