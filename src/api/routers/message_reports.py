"""HTTP-адаптер скарг на повідомлення чату (ADR-005)."""

from datetime import datetime
from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from pydantic import BaseModel, ConfigDict, Field

from src.api.deps import get_message_report_service, require_current_user
from src.api.routers.moderation import require_moderator
from src.api.schemas.listings import ErrorResponse
from src.domain.exceptions import (
    ComplaintConflictError,
    ComplaintNotFoundError,
    ConversationNotFoundError,
    DuplicateComplaintError,
    InvalidComplaintError,
    ModerationForbiddenError,
)
from src.domain.message_reports import (
    MESSAGE_REPORT_DETAILS_MAX_LENGTH,
    MESSAGE_REPORT_NOTE_MAX_LENGTH,
    MessageReportReason,
    MessageReportStatus,
)
from src.domain.users import CurrentUser
from src.services.message_reports import MessageReportService, MessageReportView

router = APIRouter(tags=["Chat reports"])

_UNAUTHORIZED = {
    401: {"model": ErrorResponse, "description": "Немає валідної сесії"},
}
_FORBIDDEN = {
    403: {"model": ErrorResponse, "description": "Немає прав"},
}
_NOT_FOUND = {
    404: {"model": ErrorResponse, "description": "Не знайдено"},
}
_CONFLICT = {
    409: {"model": ErrorResponse, "description": "Конфлікт"},
}

# Лише відповіді, які кожен маршрут справді може повернути.
_REPORT_ERRORS = {**_UNAUTHORIZED, **_FORBIDDEN, **_NOT_FOUND, **_CONFLICT}
_LIST_ERRORS = {**_UNAUTHORIZED, **_FORBIDDEN}
_RESOLVE_ERRORS = {**_UNAUTHORIZED, **_FORBIDDEN, **_NOT_FOUND, **_CONFLICT}


class MessageReportCreateRequest(BaseModel):
    """Тіло скарги на повідомлення; автор береться із сесії."""

    model_config = ConfigDict(extra="forbid")

    reason: MessageReportReason
    details: str = Field(default="", max_length=MESSAGE_REPORT_DETAILS_MAX_LENGTH)


class MessageReportResolveRequest(BaseModel):
    """Рішення адміністратора за скаргою."""

    model_config = ConfigDict(extra="forbid")

    status: MessageReportStatus
    note: str = Field(default="", max_length=MESSAGE_REPORT_NOTE_MAX_LENGTH)


class MessageReportResponse(BaseModel):
    """Скарга на повідомлення для адмін-панелі."""

    id: UUID
    message_id: UUID
    conversation_id: UUID
    reporter_id: UUID
    reporter_name: str | None = None
    reported_user_id: UUID
    reported_name: str | None = None
    body_snapshot: str
    reason: MessageReportReason
    details: str
    status: MessageReportStatus
    created_at: datetime
    resolved_at: datetime | None = None
    resolution_note: str = ""


def _to_response(view: MessageReportView) -> MessageReportResponse:
    item = view.report
    return MessageReportResponse(
        id=item.id,
        message_id=item.message_id,
        conversation_id=item.conversation_id,
        reporter_id=item.reporter_id,
        reporter_name=view.reporter_name,
        reported_user_id=item.reported_user_id,
        reported_name=view.reported_name,
        body_snapshot=item.body_snapshot,
        reason=item.reason,
        details=item.details,
        status=item.status,
        created_at=item.created_at,
        resolved_at=item.resolved_at,
        resolution_note=item.resolution_note,
    )


def _http_error(exc: Exception) -> HTTPException:
    if isinstance(exc, (ConversationNotFoundError, ComplaintNotFoundError)):
        code = status.HTTP_404_NOT_FOUND
    elif isinstance(exc, ModerationForbiddenError):
        code = status.HTTP_403_FORBIDDEN
    elif isinstance(exc, (DuplicateComplaintError, ComplaintConflictError)):
        code = status.HTTP_409_CONFLICT
    else:
        code = status.HTTP_422_UNPROCESSABLE_CONTENT
    return HTTPException(
        status_code=code,
        detail=str(exc),
        headers={"Cache-Control": "no-store"},
    )


@router.post(
    "/conversations/{conversation_id}/messages/{message_id}/report",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Поскаржитися на повідомлення",
    description=(
        "Учасник розмови скаржиться на повідомлення співрозмовника. Одна скарга "
        "від користувача на повідомлення; не-учасник і невідоме повідомлення "
        "дають однакову 404."
    ),
    responses=_REPORT_ERRORS,
)
def report_message(
    conversation_id: UUID,
    message_id: UUID,
    body: MessageReportCreateRequest,
    response: Response,
    current_user: CurrentUser = Depends(require_current_user),
    service: MessageReportService = Depends(get_message_report_service),
) -> None:
    try:
        service.submit(
            current_user, conversation_id, message_id, body.reason, body.details
        )
    except (
        ConversationNotFoundError,
        DuplicateComplaintError,
        InvalidComplaintError,
    ) as exc:
        raise _http_error(exc) from exc
    response.headers["Cache-Control"] = "no-store"


@router.get(
    "/admin/message-reports",
    response_model=list[MessageReportResponse],
    summary="Список скарг на повідомлення (адміністратор)",
    description="Відкриті скарги першими; необов'язковий фільтр `status`.",
    responses=_LIST_ERRORS,
)
def list_message_reports(
    response: Response,
    status_filter: Optional[MessageReportStatus] = Query(None, alias="status"),
    admin: CurrentUser = Depends(require_moderator),
    service: MessageReportService = Depends(get_message_report_service),
) -> list[MessageReportResponse]:
    response.headers["Cache-Control"] = "no-store"
    try:
        views = service.list_reports(admin, status_filter)
    except ModerationForbiddenError as exc:
        raise _http_error(exc) from exc
    return [_to_response(view) for view in views]


@router.post(
    "/admin/message-reports/{report_id}/resolve",
    response_model=MessageReportResponse,
    summary="Розглянути скаргу на повідомлення (адміністратор)",
    description="Позначає скаргу RESOLVED або DISMISSED із необов'язковою приміткою.",
    responses=_RESOLVE_ERRORS,
)
def resolve_message_report(
    report_id: UUID,
    body: MessageReportResolveRequest,
    response: Response,
    admin: CurrentUser = Depends(require_moderator),
    service: MessageReportService = Depends(get_message_report_service),
) -> MessageReportResponse:
    response.headers["Cache-Control"] = "no-store"
    try:
        report = service.resolve(admin, report_id, body.status, body.note)
    except (
        ComplaintNotFoundError,
        ComplaintConflictError,
        InvalidComplaintError,
        ModerationForbiddenError,
    ) as exc:
        raise _http_error(exc) from exc
    return _to_response(service.view(report))
