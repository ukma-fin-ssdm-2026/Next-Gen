"""Залежності FastAPI: збирає сервіси на краю застосунку."""

from src.repositories.categories import InMemoryCategoryRepository
from src.repositories.favorites import InMemoryFavoriteRepository
from src.repositories.listings import InMemoryListingRepository
from src.services.categories import CategoryService
from src.services.favorites import FavoriteService
from src.services.listings import ListingService

category_repository = InMemoryCategoryRepository.with_seed()
listing_repository = InMemoryListingRepository.with_seed()
favorite_repository = InMemoryFavoriteRepository()
category_service = CategoryService(category_repository)
listing_service = ListingService(listing_repository, favorites=favorite_repository)
favorite_service = FavoriteService(favorite_repository, listing_repository)


def get_category_service() -> CategoryService:
    """Повертає Category Service для ін'єкції в роутери."""
    return category_service


def get_listing_service() -> ListingService:
    """Повертає Listing Service для ін'єкції в роутери."""
    return listing_service


def get_favorite_service() -> FavoriteService:
    """Повертає Favorite Service, що ділить сховища з Listing Service."""
    return favorite_service
