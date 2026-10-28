"""Модульні тести Seller Contact Service (FR-010, SEC-002). Підхід AAA."""

from uuid import uuid4

import pytest

from src.domain.exceptions import ListingNotFoundError, ListingUnauthorizedError
from src.domain.listings import SEED_LISTING_ID, WITHDRAWN_LISTING_ID
from src.repositories.listings import InMemoryListingRepository
from src.services.contacts import SellerContactService


@pytest.fixture
def service() -> SellerContactService:
    return SellerContactService(InMemoryListingRepository.with_seed())


def test_identified_viewer_gets_contact_of_active_listing(
    service: SellerContactService,
) -> None:
    """[TP-018] [FR-010] [SEC-002]
    Ідентифікований користувач отримує контакт продавця активного оголошення.
    """
    # Act
    contact = service.get_contact(uuid4(), SEED_LISTING_ID)
    # Assert
    assert contact.listing_id == SEED_LISTING_ID
    assert contact.contact == "@student_ukma"


def test_missing_viewer_is_rejected_before_lookup(
    service: SellerContactService,
) -> None:
    """[TP-018] [FR-010] [SEC-002] Без ідентичності контакт не повертається."""
    with pytest.raises(ListingUnauthorizedError):
        service.get_contact(None, SEED_LISTING_ID)


def test_withdrawn_listing_contact_is_not_found(
    service: SellerContactService,
) -> None:
    """[TP-018] [FR-010] [SEC-002] Контакт знятого оголошення не видається (404)."""
    with pytest.raises(ListingNotFoundError):
        service.get_contact(uuid4(), WITHDRAWN_LISTING_ID)


def test_unknown_listing_contact_is_not_found(service: SellerContactService) -> None:
    """[TP-018] [FR-010] Неіснуюче оголошення дає ListingNotFoundError."""
    with pytest.raises(ListingNotFoundError):
        service.get_contact(uuid4(), uuid4())
