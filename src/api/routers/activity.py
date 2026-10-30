"""HTTP-адаптер журналів дій користувачів та адміністраторів (FR-018)."""

from fastapi import APIRouter, Depends, HTTPException, Query, status

from src.api.deps import get_activity_service
from src.api.routers.moderation import require_moderator
from src.api.schemas.listings import ErrorResponse
from src.api.schemas.support import LogEntryResponse
from src.domain.exceptions import ModerationForbiddenError
from src.domain.users import CurrentUser
from src.services.activity import ActivityLogService, LogEntry

router = APIRouter(prefix="/admin/logs", tags=["Activity log"])

_ERRORS = {
    401: {"model": ErrorResponse, "description": "Немає валідної сесії"},
    403: {"model": ErrorResponse, "description": "Немає ролі ADMIN"},
}


def _to_response(entry: LogEntry) -> LogEntryResponse:
    return LogEntryResponse(
        id=entry.id,
        created_at=entry.created_at,
        actor_id=entry.actor_id,
        actor_email=entry.actor_email,
        action_type=entry.action_type,
        listing_id=entry.listing_id,
        target_user_id=entry.target_user_id,
        target_email=entry.target_email,
        details=entry.details,
    )


@router.get(
    "/users",
    response_model=list[LogEntryResponse],
    summary="Журнал дій користувачів (адміністратор)",
    description="Створення, зміна і зняття оголошень, обране, скарги, звернення.",
    responses=_ERRORS,
)
def user_log(
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=500),
    admin: CurrentUser = Depends(require_moderator),
    service: ActivityLogService = Depends(get_activity_service),
) -> list[LogEntryResponse]:
    try:
        return [_to_response(e) for e in service.user_log(admin, skip, limit)]
    except ModerationForbiddenError as exc:
        raise HTTPException(status.HTTP_403_FORBIDDEN, detail=str(exc)) from exc


@router.get(
    "/admins",
    response_model=list[LogEntryResponse],
    summary="Журнал дій адміністраторів (адміністратор)",
    description=(
        "Блокування, розблокування, зняття оголошень, розгляд категорій, скарг "
        "і звернень."
    ),
    responses=_ERRORS,
)
def admin_log(
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=500),
    admin: CurrentUser = Depends(require_moderator),
    service: ActivityLogService = Depends(get_activity_service),
) -> list[LogEntryResponse]:
    try:
        return [_to_response(e) for e in service.admin_log(admin, skip, limit)]
    except ModerationForbiddenError as exc:
        raise HTTPException(status.HTTP_403_FORBIDDEN, detail=str(exc)) from exc
