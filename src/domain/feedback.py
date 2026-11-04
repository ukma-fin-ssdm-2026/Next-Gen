"""Звернення користувачів до адміністрації (FR-017)."""

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from uuid import UUID, uuid4

from src.domain.exceptions import InvalidFeedbackError
from src.domain.listings import utc_now

FEEDBACK_SUBJECT_MIN_LENGTH = 3
FEEDBACK_SUBJECT_MAX_LENGTH = 120
FEEDBACK_MESSAGE_MIN_LENGTH = 10
FEEDBACK_MESSAGE_MAX_LENGTH = 2000


class FeedbackStatus(str, Enum):
    """Стан звернення: нове чи опрацьоване адміністратором."""

    NEW = "NEW"
    RESOLVED = "RESOLVED"


def _validate_text_length(
    value: str, min_len: int, max_len: int, field_name: str
) -> None:
    """Перевіряє межі довжини текстового поля (Extract Method)."""
    if not (min_len <= len(value) <= max_len):
        raise InvalidFeedbackError(
            f"{field_name} має містити від {min_len} до {max_len} символів"
        )


@dataclass
class Feedback:
    """Звернення користувача: тема, текст і стан опрацювання."""

    user_id: UUID
    subject: str
    message: str
    status: FeedbackStatus = FeedbackStatus.NEW
    id: UUID = field(default_factory=uuid4)
    created_at: datetime = field(default_factory=utc_now)
    resolved_by: UUID | None = None
    resolved_at: datetime | None = None

    def __post_init__(self) -> None:
        self.subject = self.subject.strip()
        self.message = self.message.strip()
        _validate_text_length(
            self.subject,
            FEEDBACK_SUBJECT_MIN_LENGTH,
            FEEDBACK_SUBJECT_MAX_LENGTH,
            "Тема",
        )
        _validate_text_length(
            self.message,
            FEEDBACK_MESSAGE_MIN_LENGTH,
            FEEDBACK_MESSAGE_MAX_LENGTH,
            "Повідомлення",
        )
