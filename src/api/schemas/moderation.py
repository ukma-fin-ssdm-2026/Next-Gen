"""Схеми адміністративної модерації оголошень і користувачів (FR-011, FR-013)."""

from datetime import datetime
from typing import Annotated
from uuid import UUID

from pydantic import BaseModel, Field, StringConstraints

from src.domain.moderation import (
    MODERATION_REASON_MAX_LENGTH,
    MODERATION_REASON_MIN_LENGTH,
    ModerationActionType,
)

ModerationReason = Annotated[
    str,
    StringConstraints(
        strip_whitespace=True,
        min_length=MODERATION_REASON_MIN_LENGTH,
        max_length=MODERATION_REASON_MAX_LENGTH,
    ),
]


class ModerationWithdrawRequest(BaseModel):
    """Тіло запиту містить лише причину; модератор береться із сесії."""

    reason: ModerationReason = Field(
        ...,
        description=(
            "Причина зняття, від "
            f"{MODERATION_REASON_MIN_LENGTH} до {MODERATION_REASON_MAX_LENGTH} "
            "символів після обрізання пробілів"
        ),
        examples=["Оголошення порушує правила: продаж заборонених товарів"],
    )


class UserModerationRequest(BaseModel):
    """Тіло блокування/розблокування містить лише причину; адмін — із сесії."""

    reason: ModerationReason = Field(
        ...,
        description=(
            "Причина дії, від "
            f"{MODERATION_REASON_MIN_LENGTH} до {MODERATION_REASON_MAX_LENGTH} "
            "символів після обрізання пробілів"
        ),
        examples=["Систематичне розміщення заборонених товарів"],
    )


class ModerationActionResponse(BaseModel):
    id: UUID = Field(..., description="Ідентифікатор запису модерації")
    listing_id: UUID | None = Field(None, description="Зняте оголошення")
    target_user_id: UUID | None = Field(
        None, description="Заблокований або розблокований користувач"
    )
    moderator_id: UUID = Field(..., description="Адміністратор із серверної сесії")
    action_type: ModerationActionType = Field(..., description="Тип дії")
    reason: str = Field(..., description="Зафіксована причина")
    created_at: datetime = Field(..., description="Час виконання дії (UTC)")
