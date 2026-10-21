"""Property-based тести інваріантів каталогу за допомогою Hypothesis (Бонус)."""

from uuid import uuid4

from hypothesis import given, settings
from hypothesis import strategies as st
import pytest

from src.domain.exceptions import InvalidPriceRangeError
from src.domain.listings import SEED_CATEGORY_ID, Listing, ListingStatus
from src.repositories.listings import InMemoryListingRepository
from src.services.listings import ListingService


@settings(max_examples=50)
@given(
    min_price=st.floats(min_value=0.0, max_value=1000.0),
    max_price=st.floats(min_value=0.0, max_value=1000.0),
)
def test_property_price_filter_invariant(min_price: float, max_price: float) -> None:
    """Властивість: при min_price <= max_price всі товари потрапляють в діапазон;

    при min_price > max_price завжди викидається InvalidPriceRangeError.
    """
    owner_id = uuid4()
    sample_prices = [0.0, 50.0, 100.0, 250.0, 500.0, 750.0, 1000.0]
    listings = [
        Listing(
            title=f"Товар {p}",
            description="Тестовий опис для Hypothesis",
            price=p,
            category_id=SEED_CATEGORY_ID,
            contact="@student",
            user_id=owner_id,
            status=ListingStatus.ACTIVE,
        )
        for p in sample_prices
    ]
    service = ListingService(InMemoryListingRepository(listings))

    if min_price > max_price:
        with pytest.raises(InvalidPriceRangeError):
            service.list_public(min_price=min_price, max_price=max_price)
    else:
        results = service.list_public(min_price=min_price, max_price=max_price)
        for item in results:
            assert min_price <= item.price <= max_price
