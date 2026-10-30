"""HTTP-адаптер адміністративної модерації оголошень і користувачів (FR-011, FR-013).

Роль ADMIN перевіряється лише з `CurrentUser`, який `require_current_user`
перечитує з локального запису користувача. Поля запиту, заголовки на кшталт
`X-Actor-Id` чи `role=ADMIN` у тілі ролі не надають.
"""

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status

from src.api.deps import (
    get_moderation_service,
    get_user_moderation_service,
    require_current_user,
)
from src.api.schemas.listings import ApiValidationErrorResponse, ErrorResponse
from src.api.schemas.support import BlockedUserResponse
from src.api.schemas.moderation import (
    ModerationActionResponse,
    ModerationWithdrawRequest,
    UserEmailModerationRequest,
    UserModerationRequest,
)
from src.domain.exceptions import (
    InvalidModerationReasonError,
    InvalidUserModerationError,
    ListingNotFoundError,
    ModerationForbiddenError,
    UserNotFoundError,
)
from src.domain.moderation import ModerationAction
from src.domain.users import CurrentUser, UserRole
from src.services.moderation import ModerationService
from src.services.user_moderation import UserModerationService

router = APIRouter(prefix="/admin", tags=["Moderation"])


def _action_response(action: ModerationAction) -> ModerationActionResponse:
    return ModerationActionResponse(
        id=action.id,
        listing_id=action.listing_id,
        target_user_id=action.target_user_id,
        suggestion_id=action.suggestion_id,
        moderator_id=action.moderator_id,
        action_type=action.action_type,
        reason=action.reason,
        created_at=action.created_at,
    )


def require_moderator(
    current_user: CurrentUser = Depends(require_current_user),
) -> CurrentUser:
    """401 без сесії (з require_current_user), 403 без ролі ADMIN."""
    if current_user.role != UserRole.ADMIN:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Дія дозволена лише адміністраторам",
        )
    return current_user


@router.post(
    "/listings/{listing_id}/withdraw",
    response_model=ModerationActionResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Зняти чуже оголошення з публікації (модерація)",
    description=(
        "Адміністратор знімає активне оголошення з обов'язковою причиною (FR-011). "
        "Оголошення переходить у WITHDRAWN, зникає з каталогу та обраного, а в "
        "журналі модерації створюється незмінний запис. Фізичного видалення немає."
    ),
    responses={
        401: {"model": ErrorResponse, "description": "Немає валідної сесії"},
        403: {
            "model": ErrorResponse,
            "description": "Немає ролі ADMIN або обліковий запис заблоковано",
        },
        404: {
            "model": ErrorResponse,
            "description": "Оголошення не існує або вже зняте",
        },
        422: {"model": ApiValidationErrorResponse, "description": "Validation Error"},
    },
)
def withdraw_listing(
    listing_id: UUID,
    request: ModerationWithdrawRequest,
    moderator: CurrentUser = Depends(require_moderator),
    service: ModerationService = Depends(get_moderation_service),
) -> ModerationActionResponse:
    try:
        action = service.withdraw_listing(moderator, listing_id, request.reason)
    except ModerationForbiddenError as exc:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(exc))
    except ListingNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))
    except InvalidModerationReasonError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail=[
                {"loc": ["body", "reason"], "msg": str(exc), "type": "value_error"}
            ],
        )
    return _action_response(action)


_USER_ACTION_RESPONSES = {
    401: {"model": ErrorResponse, "description": "Немає валідної сесії"},
    403: {
        "model": ErrorResponse,
        "description": "Немає ролі ADMIN або обліковий запис заблоковано",
    },
    404: {"model": ErrorResponse, "description": "Користувача не знайдено"},
    409: {
        "model": ErrorResponse,
        "description": (
            "Дія неможлива: самоблокування, адміністратор або вже в такому стані"
        ),
    },
    422: {"model": ApiValidationErrorResponse, "description": "Validation Error"},
}


def _run_user_action(call, target, request: UserModerationRequest):
    try:
        action = call(target, request.reason)
    except ModerationForbiddenError as exc:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(exc))
    except UserNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))
    except InvalidUserModerationError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc))
    except InvalidModerationReasonError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail=[
                {"loc": ["body", "reason"], "msg": str(exc), "type": "value_error"}
            ],
        )
    return _action_response(action)


@router.post(
    "/users/{user_id}/block",
    response_model=ModerationActionResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Заблокувати користувача (модерація)",
    description=(
        "Адміністратор блокує обліковий запис з обов'язковою причиною (FR-013). "
        "Усі сесії користувача відкликаються, вхід і мутуючі дії стають "
        "недоступними (403), оголошення не видаляються. Не можна заблокувати "
        "себе або іншого адміністратора."
    ),
    responses=_USER_ACTION_RESPONSES,
)
def block_user(
    user_id: UUID,
    request: UserModerationRequest,
    moderator: CurrentUser = Depends(require_moderator),
    service: UserModerationService = Depends(get_user_moderation_service),
) -> ModerationActionResponse:
    return _run_user_action(
        lambda uid, reason: service.block_user(moderator, uid, reason),
        user_id,
        request,
    )


@router.post(
    "/users/{user_id}/unblock",
    response_model=ModerationActionResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Розблокувати користувача (модерація)",
    description=(
        "Адміністратор знімає блокування з обов'язковою причиною (FR-013); "
        "користувач може знову входити через Microsoft Entra ID."
    ),
    responses=_USER_ACTION_RESPONSES,
)
def unblock_user(
    user_id: UUID,
    request: UserModerationRequest,
    moderator: CurrentUser = Depends(require_moderator),
    service: UserModerationService = Depends(get_user_moderation_service),
) -> ModerationActionResponse:
    return _run_user_action(
        lambda uid, reason: service.unblock_user(moderator, uid, reason),
        user_id,
        request,
    )


@router.post(
    "/users/block-by-email",
    response_model=ModerationActionResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Заблокувати користувача за email (модерація)",
    description=(
        "Те саме, що блокування за ID (FR-013), але користувач знаходиться за "
        "адресою @ukma.edu.ua з тіла запиту. Працює лише для тих, хто вже входив "
        "на сайт; для невідомої адреси повертається 404. Адреса не потрапляє в URL."
    ),
    responses=_USER_ACTION_RESPONSES,
)
def block_user_by_email(
    request: UserEmailModerationRequest,
    moderator: CurrentUser = Depends(require_moderator),
    service: UserModerationService = Depends(get_user_moderation_service),
) -> ModerationActionResponse:
    return _run_user_action(
        lambda email, reason: service.block_user_by_email(moderator, email, reason),
        request.email,
        request,
    )


@router.post(
    "/users/unblock-by-email",
    response_model=ModerationActionResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Розблокувати користувача за email (модерація)",
    description="Знімає блокування за адресою @ukma.edu.ua з тіла запиту (FR-013).",
    responses=_USER_ACTION_RESPONSES,
)
def unblock_user_by_email(
    request: UserEmailModerationRequest,
    moderator: CurrentUser = Depends(require_moderator),
    service: UserModerationService = Depends(get_user_moderation_service),
) -> ModerationActionResponse:
    return _run_user_action(
        lambda email, reason: service.unblock_user_by_email(moderator, email, reason),
        request.email,
        request,
    )


@router.get(
    "/users/blocked",
    response_model=list[BlockedUserResponse],
    summary="Список заблокованих користувачів (адміністратор)",
    description=(
        "Усі заблоковані користувачі з причиною та часом блокування; дані "
        "зберігаються в БД і переживають перезапуск (FR-013)."
    ),
    responses={
        401: {"model": ErrorResponse, "description": "Немає валідної сесії"},
        403: {"model": ErrorResponse, "description": "Немає ролі ADMIN"},
    },
)
def list_blocked_users(
    moderator: CurrentUser = Depends(require_moderator),
    service: UserModerationService = Depends(get_user_moderation_service),
) -> list[BlockedUserResponse]:
    try:
        users = service.list_blocked(moderator)
    except ModerationForbiddenError as exc:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(exc))
    return [
        BlockedUserResponse(
            user_id=user.user_id,
            email=user.email,
            display_name=user.display_name,
            reason=user.block_reason,
            blocked_at=user.blocked_at,
        )
        for user in users
    ]
