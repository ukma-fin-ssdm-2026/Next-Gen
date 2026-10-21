"""Сутність оголошення та статуси каталогу."""

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from uuid import UUID, uuid4


class ListingStatus(str, Enum):
    """Допустимі статуси оголошення (FR-004, FR-005, FR-006)."""

    ACTIVE = "ACTIVE"
    WITHDRAWN = "WITHDRAWN"
    RESERVED = "RESERVED"
    SOLD = "SOLD"


class ListingSortOrder(str, Enum):
    """Порядок сортування каталогу за датою публікації (FR-008)."""

    NEWEST = "newest"
    OLDEST = "oldest"


def utc_now() -> datetime:
    """Повертає поточний час у UTC."""
    return datetime.now(timezone.utc)


@dataclass
class Listing:
    """Оголошення маркетплейсу. Поле contact не потрапляє в публічні відповіді."""

    title: str
    description: str
    price: float
    category_id: UUID
    contact: str
    user_id: UUID
    id: UUID = field(default_factory=uuid4)
    status: ListingStatus = ListingStatus.ACTIVE
    created_at: datetime = field(default_factory=utc_now)
    updated_at: datetime = field(default_factory=utc_now)

    def is_public(self) -> bool:
        """Чи має оголошення потрапляти в каталог покупця."""
        return self.status == ListingStatus.ACTIVE


SEED_OWNER_ID = UUID("87654321-4321-8765-4321-876543210987")
SEED_LISTING_ID = UUID("3fa85f64-5717-4562-b3fc-2c963f66afa6")
SEED_CATEGORY_ID = UUID("12345678-1234-5678-1234-567812345678")
WITHDRAWN_LISTING_ID = UUID("aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee")


def build_seed_listings() -> list[Listing]:
    """Початкові дані прототипу: одне активне і одне зняте оголошення."""
    return [
        Listing(
            id=SEED_LISTING_ID,
            title="Худі з логотипом НаУКМА",
            description="Худі в ідеальному стані, розмір M. Продаю, бо не ношу.",
            price=150.0,
            category_id=SEED_CATEGORY_ID,
            contact="@student_ukma",
            user_id=SEED_OWNER_ID,
            status=ListingStatus.ACTIVE,
        ),
        Listing(
            id=WITHDRAWN_LISTING_ID,
            title="Старий конспект з дискретної математики",
            description="Знято з публікації: товар уже передано одногрупнику.",
            price=50.0,
            category_id=SEED_CATEGORY_ID,
            contact="@hidden_contact",
            user_id=SEED_OWNER_ID,
            status=ListingStatus.WITHDRAWN,
        ),
    ]
