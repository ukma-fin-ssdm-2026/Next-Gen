"""Pydantic-схеми ресурсу Listing. Валідація входу на межі API."""

from datetime import datetime
from typing import Any, Optional
from uuid import UUID

from pydantic import BaseModel, Field, field_validator


class ListingBase(BaseModel):
    title: str = Field(
        ...,
        min_length=3,
        max_length=100,
        description="Назва оголошення",
        examples=["Худі з логотипом НаУКМА"],
    )
    description: str = Field(
        ...,
        min_length=10,
        max_length=2000,
        description="Детальний опис товару",
        examples=["Худі в ідеальному стані, розмір M. Продаю, бо не ношу."],
    )
    price: float = Field(..., ge=0, description="Ціна в гривнях", examples=[150.0])
    category_id: UUID = Field(
        ...,
        description="ID категорії",
        examples=["3fa85f64-5717-4562-b3fc-2c963f66afa6"],
    )


class ListingCreate(ListingBase):
    contact: str = Field(
        ...,
        min_length=3,
        max_length=200,
        description="Контактні дані (пошта або Telegram)",
        examples=["@student_ukma"],
    )


class ListingUpdate(BaseModel):
    title: Optional[str] = Field(None, min_length=3, max_length=100)
    description: Optional[str] = Field(None, min_length=10, max_length=2000)
    price: Optional[float] = Field(None, ge=0)
    contact: Optional[str] = Field(None, min_length=3, max_length=200)

    @field_validator("title", "description", "price", "contact", mode="before")
    @classmethod
    def reject_null(cls, value: Any) -> Any:
        if value is None:
            raise ValueError("Поле не може бути null")
        return value


class ListingPublicResponse(ListingBase):
    id: UUID = Field(..., description="Унікальний ідентифікатор оголошення")
    user_id: UUID = Field(..., description="ID автора")
    status: str = Field(..., description="Статус оголошення", examples=["ACTIVE"])
    created_at: datetime = Field(..., description="Дата створення")
    updated_at: datetime = Field(..., description="Дата останнього оновлення")


class ListingResponse(ListingPublicResponse):
    contact: str = Field(..., description="Контактні дані (пошта або Telegram)")


class ErrorResponse(BaseModel):
    detail: str = Field(
        ..., description="Опис помилки", examples=["Оголошення не знайдено"]
    )
