"""Незмінний запис адміністративної дії модерації (FR-011, FR-013, FR-015)."""

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from uuid import UUID, uuid4

from src.domain.exceptions import InvalidModerationReasonError
from src.domain.listings import utc_now

MODERATION_REASON_MIN_LENGTH = 5
MODERATION_REASON_MAX_LENGTH = 500


class ModerationActionType(str, Enum):
    """Типи дій модерації над оголошенням, користувачем і пропозицією категорії."""

    WITHDRAW_LISTING = "WITHDRAW_LISTING"
    BLOCK_USER = "BLOCK_USER"
    UNBLOCK_USER = "UNBLOCK_USER"
    APPROVE_CATEGORY = "APPROVE_CATEGORY"
    REJECT_CATEGORY = "REJECT_CATEGORY"


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
    """Аудит-запис: хто, що, над яким об'єктом, чому і коли.

    `frozen=True`: після створення запис не змінюється (історія модерації).
    Для `WITHDRAW_LISTING` обов'язковий `listing_id`, для `BLOCK_USER` та
    `UNBLOCK_USER` — `target_user_id`, для `APPROVE_CATEGORY` та
    `REJECT_CATEGORY` — `suggestion_id`.
    """

    moderator_id: UUID
    action_type: ModerationActionType
    reason: str
    listing_id: UUID | None = None
    target_user_id: UUID | None = None
    suggestion_id: UUID | None = None
    id: UUID = field(default_factory=uuid4)
    created_at: datetime = field(default_factory=utc_now)

    def __post_init__(self) -> None:
        normalize_moderation_reason(self.reason)
        if self.action_type == ModerationActionType.WITHDRAW_LISTING:
            valid = (
                self.listing_id is not None
                and self.target_user_id is None
                and self.suggestion_id is None
            )
        elif self.action_type in (
            ModerationActionType.BLOCK_USER,
            ModerationActionType.UNBLOCK_USER,
        ):
            valid = (
                self.target_user_id is not None
                and self.listing_id is None
                and self.suggestion_id is None
            )
        else:
            valid = (
                self.suggestion_id is not None
                and self.listing_id is None
                and self.target_user_id is None
            )
        if not valid:
            raise ValueError("Ціль дії модерації не відповідає її типу")
