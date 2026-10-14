"""Спільні фікстури: ізольований Listing Service на кожен тест."""

import pytest
from fastapi.testclient import TestClient

from src.api.deps import get_listing_service
from src.api.main import app
from src.repositories.listings import InMemoryListingRepository
from src.services.listings import ListingService


@pytest.fixture
def listing_service() -> ListingService:
    return ListingService(InMemoryListingRepository.with_seed())


@pytest.fixture
def client(listing_service: ListingService):
    app.dependency_overrides[get_listing_service] = lambda: listing_service
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()
