"""Pydantic-схеми пропозицій нових категорій та їх модерації (FR-015 / US-010)."""

from datetime import datetime
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, Field

from src.domain.category_suggestions import (
    SUGGESTION_NAME_MAX_LENGTH,
    SUGGESTION_NAME_MIN_LENGTH,
    CategorySuggestionStatus,
)


class CategorySuggestionCreateRequest(BaseModel):
    """Запит на створення пропозиції категорії; proposer_id береться із сесії."""

    name: str = Field(
        ...,
        description=(
            f"Назва пропонованої категорії ({SUGGESTION_NAME_MIN_LENGTH}–"
            f"{SUGGESTION_NAME_MAX_LENGTH} символів після обрізання пробілів)"
        ),
        examples=["Музичні інструменти"],
    )


class CategorySuggestionApproveRequest(BaseModel):
    """Необов'язкове тіло запиту на схвалення пропозиції з можливістю уточнити назву."""

    name: Optional[str] = Field(
        None,
        description="Скоригована адміністратором назва категорії",
        examples=["Музичні інструменти та аудіо"],
    )


class CategorySuggestionRejectRequest(BaseModel):
    """Тіло запиту на відхилення пропозиції категорії з обов'язковою причиною."""

    reason: str = Field(
        ...,
        description="Причина відхилення пропозиції (5–500 символів після strip)",
        examples=["Занадто вузька категорія, скористайтеся розділом «Інше»"],
    )


class CategorySuggestionResponse(BaseModel):
    """Публічне для автора / адміністратора представлення пропозиції категорії."""

    suggestion_id: UUID = Field(..., description="Унікальний ідентифікатор пропозиції")
    name: str = Field(..., description="Назва пропонованої категорії")
    proposer_id: UUID = Field(..., description="ID користувача, який подав пропозицію")
    status: CategorySuggestionStatus = Field(
        ..., description="Поточний статус розгляду (PENDING, APPROVED, REJECTED)"
    )
    reason: Optional[str] = Field(
        None, description="Причина відхилення (заповнюється для REJECTED)"
    )
    category_id: Optional[UUID] = Field(
        None, description="ID створеної категорії (заповнюється після APPROVED)"
    )
    reviewed_by: Optional[UUID] = Field(
        None, description="ID адміністратора, який розглянув пропозицію"
    )
    created_at: datetime = Field(..., description="Час створення пропозиції (UTC)")
    reviewed_at: Optional[datetime] = Field(
        None, description="Час розгляду пропозиції адміністратором (UTC)"
    )
    listings_count: int = Field(
        0,
        ge=0,
        description="Кількість активних оголошень, прив'язаних до цієї пропозиції",
    )
