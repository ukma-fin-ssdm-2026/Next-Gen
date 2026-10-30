"""HTTP-адаптер скарг на оголошення (FR-016)."""

from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status

from src.api.deps import get_complaint_service, require_current_user
from src.api.routers.moderation import require_moderator
from src.api.schemas.listings import ErrorResponse
from src.api.schemas.support import (
    ComplaintCreateRequest,
    ComplaintResolveRequest,
    ComplaintResponse,
)
from src.domain.complaints import Complaint, ComplaintStatus
from src.domain.exceptions import (
    ComplaintConflictError,
    ComplaintNotFoundError,
    DuplicateComplaintError,
    InvalidComplaintError,
    ListingNotFoundError,
    ModerationForbiddenError,
)
from src.domain.users import CurrentUser
from src.services.complaints import ComplaintService, ComplaintView

router = APIRouter(tags=["Complaints"])

_ERRORS = {
    401: {"model": ErrorResponse, "description": "Немає валідної сесії"},
    403: {"model": ErrorResponse, "description": "Немає прав"},
    404: {"model": ErrorResponse, "description": "Не знайдено"},
    409: {"model": ErrorResponse, "description": "Конфлікт"},
}


def _to_response(view: ComplaintView) -> ComplaintResponse:
    item = view.complaint
    return ComplaintResponse(
        id=item.id,
        listing_id=item.listing_id,
        listing_title=view.listing_title,
        listing_status=view.listing_status,
        reporter_id=item.reporter_id,
        reporter_email=view.reporter_email,
        reason=item.reason,
        details=item.details,
        status=item.status,
        created_at=item.created_at,
        resolved_at=item.resolved_at,
        resolution_note=item.resolution_note,
    )


def _http_error(exc: Exception) -> HTTPException:
    if isinstance(exc, (ListingNotFoundError, ComplaintNotFoundError)):
        code = status.HTTP_404_NOT_FOUND
    elif isinstance(exc, ModerationForbiddenError):
        code = status.HTTP_403_FORBIDDEN
    elif isinstance(exc, (DuplicateComplaintError, ComplaintConflictError)):
        code = status.HTTP_409_CONFLICT
    else:
        code = status.HTTP_422_UNPROCESSABLE_CONTENT
    return HTTPException(status_code=code, detail=str(exc))


@router.post(
    "/listings/{listing_id}/complaints",
    response_model=ComplaintResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Поскаржитися на оголошення",
    description=(
        "Автентифікований користувач скаржиться на активне чуже оголошення (FR-016). "
        "Одна скарга від користувача на оголошення; скарги бачить адміністратор."
    ),
    responses=_ERRORS,
)
def submit_complaint(
    listing_id: UUID,
    body: ComplaintCreateRequest,
    current_user: CurrentUser = Depends(require_current_user),
    service: ComplaintService = Depends(get_complaint_service),
) -> ComplaintResponse:
    try:
        complaint: Complaint = service.submit(
            current_user, listing_id, body.reason, body.details
        )
    except (
        ListingNotFoundError,
        DuplicateComplaintError,
        InvalidComplaintError,
    ) as exc:
        raise _http_error(exc) from exc
    return _to_response(service.view(complaint))


@router.get(
    "/admin/complaints",
    response_model=list[ComplaintResponse],
    summary="Список скарг на оголошення (адміністратор)",
    description="Нові скарги першими; необов'язковий фільтр `status`.",
    responses=_ERRORS,
)
def list_complaints(
    status_filter: Optional[ComplaintStatus] = Query(None, alias="status"),
    admin: CurrentUser = Depends(require_moderator),
    service: ComplaintService = Depends(get_complaint_service),
) -> list[ComplaintResponse]:
    try:
        views = service.list_complaints(admin, status_filter)
    except ModerationForbiddenError as exc:
        raise _http_error(exc) from exc
    return [_to_response(view) for view in views]


@router.post(
    "/admin/complaints/{complaint_id}/resolve",
    response_model=ComplaintResponse,
    summary="Розглянути скаргу (адміністратор)",
    description="Позначає скаргу RESOLVED або DISMISSED із необов'язковою приміткою.",
    responses=_ERRORS,
)
def resolve_complaint(
    complaint_id: UUID,
    body: ComplaintResolveRequest,
    admin: CurrentUser = Depends(require_moderator),
    service: ComplaintService = Depends(get_complaint_service),
) -> ComplaintResponse:
    try:
        complaint = service.resolve(admin, complaint_id, body.status, body.note)
    except (
        ComplaintNotFoundError,
        ComplaintConflictError,
        InvalidComplaintError,
        ModerationForbiddenError,
    ) as exc:
        raise _http_error(exc) from exc
    return _to_response(service.view(complaint))
