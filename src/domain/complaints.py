"""Скарги користувачів на оголошення (FR-016)."""

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from uuid import UUID, uuid4

from src.domain.exceptions import InvalidComplaintError
from src.domain.listings import utc_now

COMPLAINT_DETAILS_MAX_LENGTH = 500
COMPLAINT_NOTE_MAX_LENGTH = 500


class ComplaintReason(str, Enum):
    """Причини скарги, які може обрати користувач."""

    SPAM = "SPAM"
    FRAUD = "FRAUD"
    PROHIBITED = "PROHIBITED"
    INAPPROPRIATE = "INAPPROPRIATE"
    WRONG_CATEGORY = "WRONG_CATEGORY"
    OTHER = "OTHER"


class ComplaintStatus(str, Enum):
    """Життєвий цикл скарги: нова, опрацьована або відхилена."""

    OPEN = "OPEN"
    RESOLVED = "RESOLVED"
    DISMISSED = "DISMISSED"


def normalize_complaint_text(value: str | None, max_length: int, label: str) -> str:
    """Обрізає пробіли й перевіряє максимальну довжину текстового поля."""
    text = (value or "").strip()
    if len(text) > max_length:
        raise InvalidComplaintError(
            f"{label} не може перевищувати {max_length} символів"
        )
    return text


@dataclass
class Complaint:
    """Скарга користувача на оголошення; змінюється лише при розгляді."""

    listing_id: UUID
    reporter_id: UUID
    reason: ComplaintReason
    details: str = ""
    status: ComplaintStatus = ComplaintStatus.OPEN
    id: UUID = field(default_factory=uuid4)
    created_at: datetime = field(default_factory=utc_now)
    resolved_by: UUID | None = None
    resolved_at: datetime | None = None
    resolution_note: str = ""

    def __post_init__(self) -> None:
        self.details = normalize_complaint_text(
            self.details, COMPLAINT_DETAILS_MAX_LENGTH, "Опис скарги"
        )
        if self.reason == ComplaintReason.OTHER and not self.details:
            raise InvalidComplaintError("Для причини «Інше» опишіть проблему")
