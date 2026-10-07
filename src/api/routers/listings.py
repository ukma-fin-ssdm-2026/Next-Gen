from fastapi import APIRouter, status, HTTPException, Query
from typing import List, Optional
from uuid import UUID, uuid4
from datetime import datetime

from src.api.schemas.listings import ListingResponse, ListingCreate, ListingUpdate, ErrorResponse

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
    response_model=List[ListingResponse],
    summary="Отримати список оголошень",
    description="Повертає список оголошень з підтримкою пагінації та фільтрації за категорією.",
)
def get_listings(
    skip: int = Query(0, ge=0, description="Кількість пропущених записів (для пагінації)"),
    limit: int = Query(10, ge=1, le=100, description="Максимальна кількість записів у відповіді"),
    category_id: Optional[UUID] = Query(None, description="Фільтр за ID категорії")
):
    return MOCK_LISTINGS

@router.post(
    "",
    response_model=ListingResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Створити оголошення",
    description="Створює нове оголошення. Повертає створений об'єкт.",
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
    response_model=ListingResponse,
    summary="Отримати оголошення за ID",
    description="Повертає детальну інформацію про конкретне оголошення.",
)
def get_listing(listing_id: UUID):
    for listing in MOCK_LISTINGS:
        if listing.id == listing_id:
            return listing
    raise HTTPException(status_code=404, detail="Оголошення не знайдено")

@router.put(
    "/{listing_id}",
    response_model=ListingResponse,
    summary="Оновити оголошення",
    description="Оновлює часткову або повну інформацію про оголошення.",
)
def update_listing(listing_id: UUID, listing_update: ListingUpdate):
    for i, listing in enumerate(MOCK_LISTINGS):
        if listing.id == listing_id:
            updated_data = listing.dict()
            update_fields = listing_update.dict(exclude_unset=True)
            updated_data.update(update_fields)
            updated_data['updated_at'] = datetime.now()
            MOCK_LISTINGS[i] = ListingResponse(**updated_data)
            return MOCK_LISTINGS[i]
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
