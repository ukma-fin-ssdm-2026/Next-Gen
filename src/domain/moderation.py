"""Незмінний запис адміністративної дії модерації (FR-011)."""

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from uuid import UUID, uuid4

from src.domain.exceptions import InvalidModerationReasonError
from src.domain.listings import utc_now

MODERATION_REASON_MIN_LENGTH = 5
MODERATION_REASON_MAX_LENGTH = 500


class ModerationActionType(str, Enum):
    """Типи адміністративних дій над оголошенням."""

    WITHDRAW_LISTING = "WITHDRAW_LISTING"


def normalize_moderation_reason(reason: str) -> str:
    """Обрізає пробіли й перевіряє межі довжини причини модерації."""
    normalized = reason.strip()
    if not (
        MODERATION_REASON_MIN_LENGTH <= len(normalized) <= MODERATION_REASON_MAX_LENGTH
    ):
        raise InvalidModerationReasonError(
            "Причина модерації має містити від "
            f"{MODERATION_REASON_MIN_LENGTH} до {MODERATION_REASON_MAX_LENGTH} "
            "символів"
        )
    return normalized


@dataclass(frozen=True)
class ModerationAction:
    """Аудит-запис: хто, що, над яким оголошенням, чому і коли зробив.

    `frozen=True`: після створення запис не змінюється (історія модерації).
    """

    moderator_id: UUID
    listing_id: UUID
    action_type: ModerationActionType
    reason: str
    id: UUID = field(default_factory=uuid4)
    created_at: datetime = field(default_factory=utc_now)

    def __post_init__(self) -> None:
        normalize_moderation_reason(self.reason)
