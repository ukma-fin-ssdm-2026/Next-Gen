"""Схеми відповідей обраного (FR-009)."""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field


class FavoriteResponse(BaseModel):
    listing_id: UUID = Field(..., description="Оголошення, збережене в обране")
    created_at: datetime = Field(..., description="Час додавання в обране")
