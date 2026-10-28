"""Pydantic-схеми для категорій (FR-012)."""

from uuid import UUID
from pydantic import BaseModel, ConfigDict, Field


class CategoryResponse(BaseModel):
    """Публічна схема категорії."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID = Field(description="Унікальний ідентифікатор категорії")
    name: str = Field(description="Назва категорії")
    slug: str = Field(description="Людинозрозумілий ідентифікатор")
    description: str | None = Field(default=None, description="Опис категорії")
    is_active: bool = Field(default=True, description="Статус активності категорії")


class CategoryCreateRequest(BaseModel):
    """Схема створення нової категорії (адміністративна дія, FR-012)."""

    name: str = Field(min_length=1, max_length=100, description="Назва категорії")
    slug: str = Field(min_length=1, max_length=100, description="Slug категорії")
    description: str | None = Field(
        default=None, max_length=500, description="Опис категорії"
    )


class CategoryUpdateRequest(BaseModel):
    """Схема часткового оновлення категорії (адміністративна дія, FR-012)."""

    name: str | None = Field(
        default=None, min_length=1, max_length=100, description="Нова назва категорії"
    )
    slug: str | None = Field(
        default=None, min_length=1, max_length=100, description="Новий slug категорії"
    )
    description: str | None = Field(
        default=None, max_length=500, description="Новий опис категорії"
    )
    is_active: bool | None = Field(
        default=None, description="Статус активності (деактивація)"
    )
