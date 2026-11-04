"""HTTP-адаптер звернень до адміністрації (FR-017)."""

from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status

from src.api.deps import get_feedback_service, require_current_user
from src.api.routers.moderation import require_moderator
from src.api.schemas.listings import ErrorResponse
from src.api.schemas.support import FeedbackCreateRequest, FeedbackResponse
from src.domain.exceptions import (
    FeedbackConflictError,
    FeedbackNotFoundError,
    InvalidFeedbackError,
    ModerationForbiddenError,
)
from src.domain.feedback import Feedback, FeedbackStatus
from src.domain.users import CurrentUser
from src.services.feedback import FeedbackService

router = APIRouter(tags=["Feedback"])

_ERRORS = {
    401: {"model": ErrorResponse, "description": "Немає валідної сесії"},
    403: {"model": ErrorResponse, "description": "Немає прав"},
    404: {"model": ErrorResponse, "description": "Не знайдено"},
    409: {"model": ErrorResponse, "description": "Конфлікт"},
}


def _to_response(item: Feedback, email: str | None) -> FeedbackResponse:
    return FeedbackResponse(
        id=item.id,
        user_id=item.user_id,
        user_email=email,
        subject=item.subject,
        message=item.message,
        status=item.status,
        created_at=item.created_at,
        resolved_at=item.resolved_at,
    )


def _http_error(exc: Exception) -> HTTPException:
    if isinstance(exc, FeedbackNotFoundError):
        code = status.HTTP_404_NOT_FOUND
    elif isinstance(exc, ModerationForbiddenError):
        code = status.HTTP_403_FORBIDDEN
    elif isinstance(exc, FeedbackConflictError):
        code = status.HTTP_409_CONFLICT
    else:
        code = status.HTTP_422_UNPROCESSABLE_CONTENT
    return HTTPException(status_code=code, detail=str(exc))


@router.post(
    "/feedback",
    response_model=FeedbackResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Написати адміністрації",
    description="Автентифікований користувач надсилає звернення з темою і текстом.",
    responses=_ERRORS,
)
def submit_feedback(
    body: FeedbackCreateRequest,
    current_user: CurrentUser = Depends(require_current_user),
    service: FeedbackService = Depends(get_feedback_service),
) -> FeedbackResponse:
    try:
        item = service.submit(current_user, body.subject, body.message)
    except InvalidFeedbackError as exc:
        raise _http_error(exc) from exc
    return _to_response(item, current_user.email)


@router.get(
    "/admin/feedback",
    response_model=list[FeedbackResponse],
    summary="Звернення до адміністрації (адміністратор)",
    description="Нові звернення першими; необов'язковий фільтр `status`.",
    responses=_ERRORS,
)
def list_feedback(
    status_filter: Optional[FeedbackStatus] = Query(None, alias="status"),
    admin: CurrentUser = Depends(require_moderator),
    service: FeedbackService = Depends(get_feedback_service),
) -> list[FeedbackResponse]:
    try:
        views = service.list_feedback(admin, status_filter)
    except ModerationForbiddenError as exc:
        raise _http_error(exc) from exc
    return [_to_response(view.feedback, view.user_email) for view in views]


@router.post(
    "/admin/feedback/{feedback_id}/resolve",
    response_model=FeedbackResponse,
    summary="Позначити звернення опрацьованим (адміністратор)",
    description="Переводить звернення зі стану NEW у RESOLVED.",
    responses=_ERRORS,
)
def resolve_feedback(
    feedback_id: UUID,
    admin: CurrentUser = Depends(require_moderator),
    service: FeedbackService = Depends(get_feedback_service),
) -> FeedbackResponse:
    try:
        item = service.resolve(admin, feedback_id)
    except (
        FeedbackNotFoundError,
        FeedbackConflictError,
        ModerationForbiddenError,
    ) as exc:
        raise _http_error(exc) from exc
    return _to_response(item, None)
