"""Схеми скарг, звернень, журналів дій і списку заблокованих (FR-013, FR-016..018)."""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field

from src.domain.complaints import (
    COMPLAINT_DETAILS_MAX_LENGTH,
    COMPLAINT_NOTE_MAX_LENGTH,
    ComplaintReason,
    ComplaintStatus,
)
from src.domain.feedback import (
    FEEDBACK_MESSAGE_MAX_LENGTH,
    FEEDBACK_MESSAGE_MIN_LENGTH,
    FEEDBACK_SUBJECT_MAX_LENGTH,
    FEEDBACK_SUBJECT_MIN_LENGTH,
    FeedbackStatus,
)


class ComplaintCreateRequest(BaseModel):
    """Тіло скарги: причина і необов'язковий опис; автор береться із сесії."""

    reason: ComplaintReason = Field(..., description="Причина скарги")
    details: str = Field(
        "",
        max_length=COMPLAINT_DETAILS_MAX_LENGTH,
        description="Опис проблеми; обов'язковий для причини OTHER",
        examples=["Фото не відповідають товару"],
    )


class ComplaintResolveRequest(BaseModel):
    """Розгляд скарги адміністратором."""

    status: ComplaintStatus = Field(..., description="RESOLVED або DISMISSED")
    note: str = Field(
        "",
        max_length=COMPLAINT_NOTE_MAX_LENGTH,
        description="Необов'язкова примітка адміністратора",
    )


class ComplaintResponse(BaseModel):
    """Скарга для адмін-панелі."""

    id: UUID
    listing_id: UUID
    listing_title: str | None = None
    listing_status: str | None = None
    reporter_id: UUID
    reporter_email: str | None = None
    reason: ComplaintReason
    details: str
    status: ComplaintStatus
    created_at: datetime
    resolved_at: datetime | None = None
    resolution_note: str = ""


class FeedbackCreateRequest(BaseModel):
    """Тіло звернення до адміністрації; автор береться із сесії."""

    subject: str = Field(
        ...,
        min_length=FEEDBACK_SUBJECT_MIN_LENGTH,
        max_length=FEEDBACK_SUBJECT_MAX_LENGTH,
        description="Тема звернення",
        examples=["Пропозиція щодо категорій"],
    )
    message: str = Field(
        ...,
        min_length=FEEDBACK_MESSAGE_MIN_LENGTH,
        max_length=FEEDBACK_MESSAGE_MAX_LENGTH,
        description="Текст звернення",
    )


class FeedbackResponse(BaseModel):
    """Звернення для користувача та адмін-панелі."""

    id: UUID
    user_id: UUID
    user_email: str | None = None
    subject: str
    message: str
    status: FeedbackStatus
    created_at: datetime
    resolved_at: datetime | None = None


class LogEntryResponse(BaseModel):
    """Рядок журналу дій користувачів або адміністраторів."""

    id: UUID
    created_at: datetime
    actor_id: UUID
    actor_email: str | None = None
    action_type: str
    listing_id: UUID | None = None
    target_user_id: UUID | None = None
    target_email: str | None = None
    details: str = ""


class BlockedUserResponse(BaseModel):
    """Заблокований користувач із причиною для адмін-панелі."""

    user_id: UUID
    email: str
    display_name: str
    reason: str | None = None
    blocked_at: datetime | None = None


class BlockedStatusResponse(BaseModel):
    """Інформація для заблокованого користувача: факт і причина блокування."""

    is_blocked: bool
    reason: str | None = None
    blocked_at: datetime | None = None
