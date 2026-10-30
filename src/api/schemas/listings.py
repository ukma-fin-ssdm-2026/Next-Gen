"""Pydantic-схеми ресурсу Listing. Валідація входу на межі API."""

from datetime import datetime
from typing import Any, Optional
from uuid import UUID

from pydantic import BaseModel, Field, field_validator, model_validator

from src.domain.listings import MAX_LISTING_PRICE, ListingCondition


class UploadedImageResponse(BaseModel):
    image_id: UUID = Field(..., description="Унікальний ідентифікатор зображення")
    storage_key: str = Field(
        ...,
        description="Серверний ключ збереженого WebP-файлу",
        examples=["11111111222233334444555555555555.webp"],
    )
    image_url: str = Field(
        ...,
        description="URL або шлях до основного нормалізованого зображення",
        examples=["/uploads/11111111222233334444555555555555.webp"],
    )
    thumbnail_url: str = Field(
        ...,
        description="URL або шлях до оптимізованого thumbnail",
        examples=["/uploads/11111111222233334444555555555555_thumb.webp"],
    )
    display_order: int = Field(
        ...,
        ge=0,
        description="Початковий порядок відображення",
        examples=[0],
    )
    width: Optional[int] = Field(
        None, description="Ширина основного зображення в пікселях"
    )
    height: Optional[int] = Field(
        None, description="Висота основного зображення в пікселях"
    )
    thumbnail_width: Optional[int] = Field(
        None, description="Ширина thumbnail в пікселях"
    )
    thumbnail_height: Optional[int] = Field(
        None, description="Висота thumbnail в пікселях"
    )


class ListingImageResponse(BaseModel):
    image_id: UUID = Field(..., description="Унікальний ідентифікатор зображення")
    image_url: str = Field(
        ...,
        description="URL або шлях до збереженого зображення",
        examples=["/uploads/11111111222233334444555555555555.webp"],
    )
    thumbnail_url: Optional[str] = Field(
        None,
        description="URL або шлях до оптимізованого thumbnail",
        examples=["/uploads/11111111222233334444555555555555_thumb.webp"],
    )
    display_order: int = Field(
        ...,
        ge=0,
        description="Порядок відображення зображення",
        examples=[0],
    )
    width: Optional[int] = Field(None, description="Ширина в пікселях")
    height: Optional[int] = Field(None, description="Висота в пікселях")
    thumbnail_width: Optional[int] = Field(None, description="Ширина thumbnail")
    thumbnail_height: Optional[int] = Field(None, description="Висота thumbnail")


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
        max_length=2000,
        description="Необов'язковий опис товару; може бути порожнім",
        examples=["Худі в ідеальному стані, розмір M. Продаю, бо не ношу."],
    )
    price: float = Field(
        ...,
        ge=0,
        le=MAX_LISTING_PRICE,
        description="Ціна в гривнях (від 0 до 100 000 000)",
        examples=[150.0],
    )
    category_id: UUID = Field(
        ...,
        description="ID категорії",
        examples=["3fa85f64-5717-4562-b3fc-2c963f66afa6"],
    )
    condition: ListingCondition = Field(
        ListingCondition.GOOD,
        description="Стан товару (NEW, LIKE_NEW, GOOD, USED, FOR_PARTS)",
        examples=[ListingCondition.GOOD],
    )


class ListingCreate(ListingBase):
    category_id: Optional[UUID] = Field(  # type: ignore[assignment]
        None,
        description=(
            "ID категорії (обов'язковий, якщо не передано suggested_category_name; "
            "при пропозиції нової категорії оголошення публікується в «Інше»)"
        ),
        examples=["3fa85f64-5717-4562-b3fc-2c963f66afa6"],
    )
    suggested_category_name: Optional[str] = Field(
        None,
        description="Назва пропонованої нової категорії (FR-015 / US-010)",
        examples=["Музичні інструменти"],
    )
    description: str = Field(
        "",
        max_length=2000,
        description="Необов'язковий опис товару; може бути порожнім",
        examples=["Худі в ідеальному стані, розмір M."],
    )
    contact: str = Field(
        ...,
        min_length=3,
        max_length=200,
        description="Контактні дані (пошта або Telegram)",
        examples=["@student_ukma"],
    )
    image_urls: list[str] = Field(
        ...,
        min_length=1,
        max_length=10,
        description=(
            "Ключі або шляхи завантажених фотографій оголошення "
            "(від 1 до 10 зображень, FR-002)"
        ),
        examples=[["/uploads/11111111222233334444555555555555.webp"]],
    )

    @model_validator(mode="after")
    def require_category_or_suggestion(self) -> "ListingCreate":
        if self.category_id is None and self.suggested_category_name is None:
            raise ValueError("Потрібно вказати category_id або suggested_category_name")
        return self


class ListingUpdate(BaseModel):
    title: Optional[str] = Field(None, min_length=3, max_length=100)
    description: Optional[str] = Field(None, max_length=2000)
    price: Optional[float] = Field(None, ge=0, le=MAX_LISTING_PRICE)
    contact: Optional[str] = Field(None, min_length=3, max_length=200)
    condition: Optional[ListingCondition] = Field(None)
    image_urls: Optional[list[str]] = Field(None, min_length=1, max_length=10)

    @field_validator(
        "title",
        "description",
        "price",
        "contact",
        "condition",
        "image_urls",
        mode="before",
    )
    @classmethod
    def reject_null(cls, value: Any) -> Any:
        if value is None:
            raise ValueError("Поле не може бути null")
        return value


class ListingPublicResponse(ListingBase):
    id: UUID = Field(..., description="Унікальний ідентифікатор оголошення")
    user_id: UUID = Field(..., description="ID автора")
    status: str = Field(..., description="Статус оголошення", examples=["ACTIVE"])
    images: list[ListingImageResponse] = Field(
        default_factory=list,
        description="Список фотографій оголошення",
    )
    created_at: datetime = Field(..., description="Дата створення")
    updated_at: datetime = Field(..., description="Дата останнього оновлення")


class ListingResponse(ListingPublicResponse):
    contact: str = Field(..., description="Контактні дані (пошта або Telegram)")
    suggested_category_name: Optional[str] = Field(
        None,
        description="Назва запропонованої категорії (лише для власника, FR-015)",
    )


class ErrorResponse(BaseModel):
    detail: str = Field(
        ..., description="Опис помилки", examples=["Оголошення не знайдено"]
    )


class ValidationErrorDetail(BaseModel):
    loc: list[str | int] = Field(
        ...,
        description="Розташування поля помилки",
        examples=[["query", "min_price"]],
    )
    msg: str = Field(
        ...,
        description="Повідомлення про помилку",
        examples=["min_price (200.0) не може перевищувати max_price (100.0)"],
    )
    type: str = Field(
        ...,
        description="Тип валідаційної помилки",
        examples=["value_error"],
    )


class ApiValidationErrorResponse(BaseModel):
    """Узгоджений формат 422 для доменних і Pydantic-помилок API."""

    detail: list[ValidationErrorDetail] = Field(
        ..., description="Список помилок валідації"
    )
