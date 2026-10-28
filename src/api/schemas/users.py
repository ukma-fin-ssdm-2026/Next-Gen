"""Схеми відповідей автентифікації."""

from uuid import UUID

from pydantic import BaseModel, Field

from src.domain.users import UserRole


class CurrentUserResponse(BaseModel):
    user_id: UUID = Field(..., description="Локальний ID користувача")
    email: str = Field(..., description="Підтверджена адреса @ukma.edu.ua")
    display_name: str = Field(..., description="Ім'я з Microsoft Entra ID")
    role: UserRole = Field(..., description="Локальна роль користувача")
