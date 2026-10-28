"""Сутність оголошення, фотографії та статуси каталогу (FR-002..FR-008)."""

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from uuid import UUID, uuid4


class ListingStatus(str, Enum):
    """Допустимі статуси оголошення (FR-004, FR-005, FR-006, FR-011)."""

    ACTIVE = "ACTIVE"
    WITHDRAWN = "WITHDRAWN"
    REMOVED_BY_MODERATOR = "REMOVED_BY_MODERATOR"
    RESERVED = "RESERVED"
    SOLD = "SOLD"


class ListingCondition(str, Enum):
    """Стан товару в оголошенні згідно з моделлю даних (FR-002)."""

    NEW = "NEW"
    LIKE_NEW = "LIKE_NEW"
    GOOD = "GOOD"
    USED = "USED"


class ListingSortOrder(str, Enum):
    """Порядок сортування каталогу за датою публікації (FR-008)."""

    NEWEST = "newest"
    OLDEST = "oldest"


def utc_now() -> datetime:
    """Повертає поточний час у UTC."""
    return datetime.now(timezone.utc)


@dataclass
class ListingImage:
    """Зображення, прикріплене до оголошення (FR-002, data-model.md)."""

    image_url: str
    display_order: int = 0
    listing_id: UUID | None = None
    image_id: UUID = field(default_factory=uuid4)


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
    condition: ListingCondition = ListingCondition.GOOD
    status: ListingStatus = ListingStatus.ACTIVE
    images: list[ListingImage] = field(default_factory=list)
    created_at: datetime = field(default_factory=utc_now)
    updated_at: datetime = field(default_factory=utc_now)

    def is_public(self) -> bool:
        """Чи має оголошення потрапляти в каталог покупця."""
        return self.status == ListingStatus.ACTIVE


SEED_OWNER_ID = UUID("87654321-4321-8765-4321-876543210987")
SEED_LISTING_ID = UUID("3fa85f64-5717-4562-b3fc-2c963f66afa6")
SEED_CATEGORY_ID = UUID("12345678-1234-5678-1234-567812345678")
WITHDRAWN_LISTING_ID = UUID("aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee")
SEED_IMAGE_ID = UUID("11111111-2222-3333-4444-555555555555")


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
            condition=ListingCondition.LIKE_NEW,
            status=ListingStatus.ACTIVE,
            images=[
                ListingImage(
                    image_id=SEED_IMAGE_ID,
                    listing_id=SEED_LISTING_ID,
                    image_url="https://baraholka.ukma.edu.ua/images/hoodie-naukma.jpg",
                    display_order=0,
                )
            ],
        ),
        Listing(
            id=WITHDRAWN_LISTING_ID,
            title="Старий конспект з дискретної математики",
            description="Знято з публікації: товар уже передано одногрупнику.",
            price=50.0,
            category_id=SEED_CATEGORY_ID,
            contact="@hidden_contact",
            user_id=SEED_OWNER_ID,
            condition=ListingCondition.GOOD,
            status=ListingStatus.WITHDRAWN,
        ),
    ]
