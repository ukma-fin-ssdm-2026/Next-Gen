"""Залежності FastAPI: збирає сервіси на краю застосунку."""

from src.repositories.listings import InMemoryListingRepository
from src.services.listings import ListingService

listing_service = ListingService(InMemoryListingRepository.with_seed())


def get_listing_service() -> ListingService:
    """Повертає Listing Service для ін'єкції в роутери."""
    return listing_service
