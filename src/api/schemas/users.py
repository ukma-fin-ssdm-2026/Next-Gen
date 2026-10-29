"""Схеми відповідей автентифікації."""

from uuid import UUID

from pydantic import BaseModel, Field

from src.domain.users import UserRole


class CurrentUserResponse(BaseModel):
    user_id: UUID = Field(..., description="Локальний ID користувача")
    email: str = Field(..., description="Підтверджена адреса @ukma.edu.ua")
    display_name: str = Field(..., description="Ім'я з Microsoft Entra ID")
    role: UserRole = Field(..., description="Локальна роль користувача")
    avatar_url: str | None = Field(None, description="URL аватарки користувача")
    contact: str | None = Field(
        None, description="Контакти за замовчуванням (лише власнику профілю)"
    )


class ProfileUpdate(BaseModel):
    """Часткове оновлення профілю: передані поля змінюються (FR-014)."""

    display_name: str | None = Field(
        None, min_length=1, max_length=100, description="Ім'я у застосунку"
    )
    contact: str | None = Field(
        None,
        max_length=300,
        description="Контакти для автопідстановки в оголошення; null або '' очищає",
    )


class PublicProfileResponse(BaseModel):
    user_id: UUID = Field(..., description="Локальний ID користувача")
    display_name: str = Field(..., description="Ім'я користувача")
    avatar_url: str | None = Field(None, description="URL аватарки користувача")
