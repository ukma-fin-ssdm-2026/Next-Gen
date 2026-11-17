"""Скарги на повідомлення чату: сутність і правила (ADR-005, FR-022)."""

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from uuid import UUID, uuid4

from src.domain.complaints import ComplaintStatus, normalize_complaint_text
from src.domain.exceptions import InvalidComplaintError
from src.domain.listings import utc_now

MESSAGE_REPORT_DETAILS_MAX_LENGTH = 300
MESSAGE_REPORT_NOTE_MAX_LENGTH = 500

# Статуси розгляду ті самі, що й у скарг на оголошення.
MessageReportStatus = ComplaintStatus


class MessageReportReason(str, Enum):
    """Причини скарги на повідомлення."""

    SPAM = "SPAM"
    FRAUD = "FRAUD"
    ABUSE = "ABUSE"
    OTHER = "OTHER"


@dataclass
class MessageReport:
    """Скарга на повідомлення зі знімком тексту.

    Знімок потрібен, бо повідомлення видаляє політика зберігання: адміністратор
    бачить, на що саме поскаржились, і після видалення оригіналу.
    """

    message_id: UUID
    conversation_id: UUID
    reporter_id: UUID
    reported_user_id: UUID
    body_snapshot: str
    reason: MessageReportReason
    details: str = ""
    status: MessageReportStatus = MessageReportStatus.OPEN
    id: UUID = field(default_factory=uuid4)
    created_at: datetime = field(default_factory=utc_now)
    resolved_by: UUID | None = None
    resolved_at: datetime | None = None
    resolution_note: str = ""

    def __post_init__(self) -> None:
        self.details = normalize_complaint_text(
            self.details, MESSAGE_REPORT_DETAILS_MAX_LENGTH, "Опис скарги"
        )
        if self.reason == MessageReportReason.OTHER and not self.details:
            raise InvalidComplaintError("Для причини «Інше» опишіть проблему")
