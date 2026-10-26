"""Спільні фікстури: ізольований Listing Service на кожен тест."""

import pytest
from fastapi.testclient import TestClient

from src.api.deps import get_listing_service
from src.api.main import app
from src.domain.listings import SEED_CATEGORY_ID
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


@pytest.fixture
def listing_payload() -> dict[str, object]:
    """Валідне тіло створення оголошення для HTTP-тестів."""
    return {
        "title": "Конспект з алгебри",
        "description": "Друкований конспект, майже не користувався.",
        "price": 80.0,
        "category_id": str(SEED_CATEGORY_ID),
        "contact": "@someone",
        "image_urls": ["https://baraholka.ukma.edu.ua/images/algebra-notes.jpg"],
    }
