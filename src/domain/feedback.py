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
        if not (
            FEEDBACK_SUBJECT_MIN_LENGTH
            <= len(self.subject)
            <= FEEDBACK_SUBJECT_MAX_LENGTH
        ):
            raise InvalidFeedbackError(
                f"Тема має містити від {FEEDBACK_SUBJECT_MIN_LENGTH} "
                f"до {FEEDBACK_SUBJECT_MAX_LENGTH} символів"
            )
        if not (
            FEEDBACK_MESSAGE_MIN_LENGTH
            <= len(self.message)
            <= FEEDBACK_MESSAGE_MAX_LENGTH
        ):
            raise InvalidFeedbackError(
                f"Повідомлення має містити від {FEEDBACK_MESSAGE_MIN_LENGTH} "
                f"до {FEEDBACK_MESSAGE_MAX_LENGTH} символів"
            )
