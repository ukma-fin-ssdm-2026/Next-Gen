"""Сутність запису в обраному (FR-009)."""

from dataclasses import dataclass, field
from datetime import datetime
from uuid import UUID

from src.domain.listings import utc_now


@dataclass(frozen=True)
class Favorite:
    """Оголошення, яке користувач зберіг в обране.

    Пара (user_id, listing_id) унікальна, як складений ключ у data-model.md.
    """

    user_id: UUID
    listing_id: UUID
    created_at: datetime = field(default_factory=utc_now)
