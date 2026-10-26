"""Тести з техніки тест-дизайну: Таблиця рішень для каталогу (Лаб 7, Бонус)."""

from uuid import UUID

import pytest

from src.domain.exceptions import InvalidPriceRangeError
from src.domain.listings import (
    SEED_CATEGORY_ID,
    SEED_LISTING_ID,
    SEED_OWNER_ID,
    Listing,
    ListingStatus,
)
from src.repositories.listings import InMemoryListingRepository
from src.services.listings import ListingService

OTHER_CATEGORY_ID = UUID("99999999-9999-9999-9999-999999999999")


@pytest.mark.parametrize(
    (
        "listing_status",
        "filter_category",
        "search_query",
        "min_price",
        "max_price",
        "expected_included",
        "raises_error",
    ),
    [
        pytest.param(
            ListingStatus.ACTIVE,
            SEED_CATEGORY_ID,
            "  ХУДІ  ",
            100.0,
            200.0,
            True,
            False,
            id="DT-01",
        ),
        pytest.param(
            ListingStatus.ACTIVE,
            SEED_CATEGORY_ID,
            "ідеальному стані",
            150.0,
            150.0,
            True,
            False,
            id="DT-02",
        ),
        pytest.param(
            ListingStatus.WITHDRAWN,
            SEED_CATEGORY_ID,
            "худі",
            100.0,
            200.0,
            False,
            False,
            id="DT-03",
        ),
        pytest.param(
            ListingStatus.ACTIVE,
            OTHER_CATEGORY_ID,
            "худі",
            100.0,
            200.0,
            False,
            False,
            id="DT-04",
        ),
        pytest.param(
            ListingStatus.ACTIVE,
            SEED_CATEGORY_ID,
            "ноутбук",
            100.0,
            200.0,
            False,
            False,
            id="DT-05",
        ),
        pytest.param(
            ListingStatus.ACTIVE,
            SEED_CATEGORY_ID,
            "худі",
            200.0,
            300.0,
            False,
            False,
            id="DT-06",
        ),
        pytest.param(
            ListingStatus.ACTIVE,
            SEED_CATEGORY_ID,
            "худі",
            250.0,
            100.0,
            False,
            True,
            id="DT-07",
        ),
    ],
)
def test_catalog_filtering_decision_table(
    listing_status: ListingStatus,
    filter_category: UUID,
    search_query: str,
    min_price: float,
    max_price: float,
    expected_included: bool,
    raises_error: bool,
) -> None:
    """Перевіряє правила таблиці рішень DT-01..DT-07 для фільтрації каталогу."""
    candidate = Listing(
        id=SEED_LISTING_ID,
        title="Худі з логотипом НаУКМА",
        description="Худі в ідеальному стані, розмір M. Продаю, бо не ношу.",
        price=150.0,
        category_id=SEED_CATEGORY_ID,
        contact="@student_ukma",
        user_id=SEED_OWNER_ID,
        status=listing_status,
    )
    service = ListingService(InMemoryListingRepository([candidate]))

    if raises_error:
        with pytest.raises(InvalidPriceRangeError):
            service.list_public(
                category_id=filter_category,
                query=search_query,
                min_price=min_price,
                max_price=max_price,
            )
    else:
        results = service.list_public(
            category_id=filter_category,
            query=search_query,
            min_price=min_price,
            max_price=max_price,
        )
        returned_ids = {item.id for item in results}
        assert (SEED_LISTING_ID in returned_ids) is expected_included
