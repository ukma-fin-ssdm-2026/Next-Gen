"""Схеми адміністративної модерації оголошень (FR-011)."""

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


class ModerationActionResponse(BaseModel):
    id: UUID = Field(..., description="Ідентифікатор запису модерації")
    listing_id: UUID = Field(..., description="Зняте оголошення")
    moderator_id: UUID = Field(..., description="Адміністратор із серверної сесії")
    action_type: ModerationActionType = Field(..., description="Тип дії")
    reason: str = Field(..., description="Зафіксована причина")
    created_at: datetime = Field(..., description="Час виконання дії (UTC)")
