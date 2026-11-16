"""Запити й відповіді HTTP API вбудованого чату (ADR-005, FR-021, FR-022)."""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class StartConversationRequest(BaseModel):
    """Запит на створення або продовження розмови зі сторінки оголошення."""

    model_config = ConfigDict(extra="forbid")

    body: str = Field(
        ...,
        description=(
            "Текст першого повідомлення (1–1000 символів після обрізання пробілів, "
            "без керівних символів)"
        ),
        examples=["Вітаю! Чи актуальне ще це оголошення?"],
    )


class SendMessageRequest(BaseModel):
    """Запит на надсилання повідомлення в наявну розмову."""

    model_config = ConfigDict(extra="forbid")

    body: str = Field(
        ...,
        description=(
            "Текст повідомлення (1–1000 символів після обрізання пробілів, "
            "без керівних символів)"
        ),
        examples=["Можемо зустрітися сьогодні біля 1-го корпусу о 15:00."],
    )
    listing_id: UUID | None = Field(
        default=None,
        description=(
            "Необов'язковий ідентифікатор активного оголошення одного з учасників "
            "розмови"
        ),
    )


class ListingCardResponse(BaseModel):
    """Безпечна картка оголошення в повідомленні (без контакту продавця)."""

    model_config = ConfigDict(from_attributes=True)

    listing_id: UUID = Field(..., description="Ідентифікатор оголошення")
    available: bool = Field(
        ...,
        description=(
            "True, якщо оголошення активне; False — якщо зняте або видалене "
            "(«Оголошення знято»)"
        ),
    )
    title: str | None = Field(
        default=None,
        description="Назва активного оголошення; null, якщо оголошення знято",
    )
    price: float | None = Field(
        default=None,
        description="Ціна активного оголошення; null, якщо оголошення знято",
    )
    image_url: str | None = Field(
        default=None,
        description=(
            "URL обкладинки активного оголошення; null, якщо знято або без фото"
        ),
    )


class MessageResponse(BaseModel):
    """Одне повідомлення розмови без контактних даних користувачів."""

    model_config = ConfigDict(from_attributes=True)

    message_id: UUID = Field(..., description="Унікальний ідентифікатор повідомлення")
    conversation_id: UUID = Field(..., description="Ідентифікатор розмови")
    sender_id: UUID = Field(..., description="Публічний ідентифікатор відправника")
    body: str = Field(..., description="Звичайний текст повідомлення")
    created_at: datetime = Field(..., description="Час створення повідомлення (UTC)")
    is_own: bool = Field(
        ..., description="True, якщо повідомлення надіслав поточний користувач"
    )
    listing: ListingCardResponse | None = Field(
        default=None,
        description="Прикріплена картка оголошення або null",
    )


class ParticipantResponse(BaseModel):
    """Публічний профіль співрозмовника без email і контактів (SEC-002)."""

    model_config = ConfigDict(from_attributes=True)

    user_id: UUID = Field(..., description="Ідентифікатор співрозмовника")
    display_name: str = Field(..., description="Відображуване ім'я співрозмовника")
    avatar_url: str | None = Field(default=None, description="URL аватарки або null")


class ConversationSummaryResponse(BaseModel):
    """Елемент списку розмов поточного користувача."""

    model_config = ConfigDict(from_attributes=True)

    conversation_id: UUID = Field(..., description="Унікальний ідентифікатор розмови")
    other: ParticipantResponse = Field(..., description="Дані співрозмовника")
    last_message: MessageResponse | None = Field(
        default=None, description="Останнє повідомлення в розмові"
    )
    last_message_at: datetime = Field(
        ..., description="Час останньої активності в розмові (UTC)"
    )
    unread_count: int = Field(
        ..., ge=0, description="Кількість непрочитаних повідомлень у цій розмові"
    )


class ConversationPageResponse(BaseModel):
    """Сторінка списку розмов із курсором наступної (старішої) сторінки."""

    model_config = ConfigDict(from_attributes=True)

    items: list[ConversationSummaryResponse] = Field(
        ..., description="Список розмов від найсвіжішої активності"
    )
    next_cursor: str | None = Field(
        default=None,
        description="Непрозорий курсор для наступної сторінки або null",
    )


class MessagePageResponse(BaseModel):
    """Сторінка повідомлень розмови з курсорами гортання і polling."""

    model_config = ConfigDict(from_attributes=True)

    items: list[MessageResponse] = Field(
        ..., description="Повідомлення у хронологічному порядку"
    )
    before_cursor: str | None = Field(
        default=None,
        description="Непрозорий курсор для завантаження старіших повідомлень або null",
    )
    after_cursor: str | None = Field(
        default=None,
        description="Непрозорий курсор для опитування (polling) нових повідомлень",
    )
    has_more: bool = Field(
        ...,
        description="True, якщо в напрямку запиту залишилися ще повідомлення",
    )


class StartConversationResponse(BaseModel):
    """Результат початку або продовження розмови зі сторінки оголошення."""

    model_config = ConfigDict(from_attributes=True)

    conversation_id: UUID = Field(..., description="Ідентифікатор розмови")
    message: MessageResponse = Field(..., description="Щойно надіслане повідомлення")
    created: bool = Field(
        ...,
        description=(
            "True, якщо розмову створено вперше; False — якщо вона вже існувала"
        ),
    )


class UnreadCountResponse(BaseModel):
    """Сумарна кількість непрочитаних повідомлень у всіх розмовах користувача."""

    unread_count: int = Field(
        ...,
        ge=0,
        description="Сумарна кількість непрочитаних повідомлень",
    )
