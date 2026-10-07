from fastapi import APIRouter, status, HTTPException, Query
from typing import List, Optional
from uuid import UUID, uuid4
from datetime import datetime
from pydantic import ValidationError

from src.api.schemas.listings import (
    ListingResponse, 
    ListingPublicResponse, 
    ListingCreate, 
    ListingUpdate, 
    ErrorResponse
)

router = APIRouter(
    prefix="/listings",
    tags=["Listings"],
    responses={
        404: {"model": ErrorResponse, "description": "Not Found"},
        422: {"description": "Validation Error"}
    }
)

# Mock data
MOCK_LISTINGS = [
    ListingResponse(
        id=UUID("3fa85f64-5717-4562-b3fc-2c963f66afa6"),
        title="Худі з логотипом НаУКМА",
        description="Худі в ідеальному стані, розмір M. Продаю, бо не ношу.",
        price=150.0,
        category_id=UUID("12345678-1234-5678-1234-567812345678"),
        contact="@student_ukma",
        user_id=UUID("87654321-4321-8765-4321-876543210987"),
        status="ACTIVE",
        created_at=datetime.now(),
        updated_at=datetime.now()
    )
]

@router.get(
    "",
    response_model=List[ListingPublicResponse],
    summary="Отримати список оголошень (публічний)",
    description="Повертає список оголошень з підтримкою пагінації та фільтрації за категорією. Не містить контактних даних.",
)
def get_listings(
    skip: int = Query(0, ge=0, description="Кількість пропущених записів (для пагінації)"),
    limit: int = Query(10, ge=1, le=100, description="Максимальна кількість записів у відповіді"),
    category_id: Optional[UUID] = Query(None, description="Фільтр за ID категорії")
):
    result = MOCK_LISTINGS
    if category_id:
        result = [item for item in result if item.category_id == category_id]
    
    return result[skip : skip + limit]

@router.post(
    "",
    response_model=ListingResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Створити оголошення",
    description="Створює нове оголошення. Повертає створений об'єкт разом з контактами.",
)
def create_listing(listing: ListingCreate):
    new_listing = ListingResponse(
        id=uuid4(),
        user_id=uuid4(),
        status="ACTIVE",
        created_at=datetime.now(),
        updated_at=datetime.now(),
        **listing.dict()
    )
    MOCK_LISTINGS.append(new_listing)
    return new_listing

@router.get(
    "/{listing_id}",
    response_model=ListingPublicResponse,
    summary="Отримати оголошення за ID (публічне)",
    description="Повертає детальну інформацію про конкретне оголошення без контактів.",
)
def get_listing(listing_id: UUID):
    for listing in MOCK_LISTINGS:
        if listing.id == listing_id:
            return listing
    raise HTTPException(status_code=404, detail="Оголошення не знайдено")

@router.patch(
    "/{listing_id}",
    response_model=ListingResponse,
    summary="Частково оновити оголошення",
    description="Оновлює часткову інформацію про оголошення.",
)
def update_listing(listing_id: UUID, listing_update: ListingUpdate):
    for i, listing in enumerate(MOCK_LISTINGS):
        if listing.id == listing_id:
            updated_data = listing.dict()
            update_fields = listing_update.dict(exclude_unset=True)
            updated_data.update(update_fields)
            updated_data['updated_at'] = datetime.now()
            try:
                # Валідація нових даних
                new_listing = ListingResponse(**updated_data)
                MOCK_LISTINGS[i] = new_listing
                return new_listing
            except ValidationError as e:
                # Повертаємо 422 замість 500, якщо часткове оновлення некоректне (напр. title: null)
                raise HTTPException(status_code=422, detail=e.errors())
    raise HTTPException(status_code=404, detail="Оголошення не знайдено")

@router.delete(
    "/{listing_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Видалити оголошення",
    description="Видаляє оголошення за ID.",
)
def delete_listing(listing_id: UUID):
    for i, listing in enumerate(MOCK_LISTINGS):
        if listing.id == listing_id:
            MOCK_LISTINGS.pop(i)
            return
    raise HTTPException(status_code=404, detail="Оголошення не знайдено")
