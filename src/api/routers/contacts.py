"""HTTP-адаптер до контакту продавця (FR-010, SEC-002).

Ідентичність покупця береться лише з серверної сесії (`require_current_user`).
Відповідь не кешується, щоб контакт не осідав у проміжних кешах.
"""

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Response, status

from src.api.deps import get_contact_service, require_current_user
from src.api.schemas.contacts import SellerContactResponse
from src.api.schemas.listings import ApiValidationErrorResponse, ErrorResponse
from src.domain.exceptions import ListingNotFoundError
from src.domain.users import CurrentUser
from src.services.contacts import SellerContactService

router = APIRouter(prefix="/listings", tags=["Contacts"])


@router.get(
    "/{listing_id}/contact",
    response_model=SellerContactResponse,
    summary="Отримати контакт продавця",
    description=(
        "Повертає контакт продавця активного оголошення автентифікованому "
        "користувачу (FR-010, SEC-002). Анонімний запит отримує 401 без контакту; "
        "неіснуюче або зняте оголошення — 404."
    ),
    responses={
        401: {"model": ErrorResponse, "description": "Немає валідної сесії"},
        403: {"model": ErrorResponse, "description": "Обліковий запис заблоковано"},
        404: {"model": ErrorResponse, "description": "Оголошення не знайдено"},
        422: {"model": ApiValidationErrorResponse, "description": "Validation Error"},
    },
)
def get_seller_contact(
    listing_id: UUID,
    response: Response,
    current_user: CurrentUser = Depends(require_current_user),
    service: SellerContactService = Depends(get_contact_service),
) -> SellerContactResponse:
    try:
        contact = service.get_contact(current_user.user_id, listing_id)
    except ListingNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)
        ) from exc
    response.headers["Cache-Control"] = "no-store"
    return SellerContactResponse(listing_id=contact.listing_id, contact=contact.contact)
