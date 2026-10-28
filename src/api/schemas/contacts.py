"""Схема відповіді з контактом продавця (FR-010, SEC-002)."""

from uuid import UUID

from pydantic import BaseModel, Field


class SellerContactResponse(BaseModel):
    listing_id: UUID = Field(
        ..., description="Оголошення, контакт продавця якого запитано"
    )
    contact: str = Field(
        ...,
        description="Контакт продавця (email або Telegram); лише для активної сесії",
        examples=["@student_ukma"],
    )
