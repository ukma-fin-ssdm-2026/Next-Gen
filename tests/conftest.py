"""Спільні фікстури: ізольований Listing Service на кожен тест."""

import pytest
from fastapi.testclient import TestClient

from src.api.deps import get_favorite_service, get_listing_service
from src.api.main import app
from src.domain.listings import SEED_CATEGORY_ID
from src.repositories.favorites import InMemoryFavoriteRepository
from src.repositories.listings import InMemoryListingRepository
from src.services.favorites import FavoriteService
from src.services.listings import ListingService


@pytest.fixture
def listing_repository() -> InMemoryListingRepository:
    return InMemoryListingRepository.with_seed()


@pytest.fixture
def favorite_repository() -> InMemoryFavoriteRepository:
    return InMemoryFavoriteRepository()


@pytest.fixture
def listing_service(
    listing_repository: InMemoryListingRepository,
    favorite_repository: InMemoryFavoriteRepository,
) -> ListingService:
    return ListingService(listing_repository, favorites=favorite_repository)


@pytest.fixture
def favorite_service(
    favorite_repository: InMemoryFavoriteRepository,
    listing_repository: InMemoryListingRepository,
) -> FavoriteService:
    return FavoriteService(favorite_repository, listing_repository)


@pytest.fixture
def client(listing_service: ListingService, favorite_service: FavoriteService):
    app.dependency_overrides[get_listing_service] = lambda: listing_service
    app.dependency_overrides[get_favorite_service] = lambda: favorite_service
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
