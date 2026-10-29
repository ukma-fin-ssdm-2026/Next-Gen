"""HTTP-адаптер адміністративної модерації оголошень (FR-011).

Роль ADMIN перевіряється лише з `CurrentUser`, який `require_current_user`
перечитує з локального запису користувача. Поля запиту, заголовки на кшталт
`X-Actor-Id` чи `role=ADMIN` у тілі ролі не надають.
"""

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status

from src.api.deps import get_moderation_service, require_current_user
from src.api.schemas.listings import ApiValidationErrorResponse, ErrorResponse
from src.api.schemas.moderation import (
    ModerationActionResponse,
    ModerationWithdrawRequest,
)
from src.domain.exceptions import (
    InvalidModerationReasonError,
    ListingNotFoundError,
    ModerationForbiddenError,
)
from src.domain.users import CurrentUser, UserRole
from src.services.moderation import ModerationService

router = APIRouter(prefix="/admin/listings", tags=["Moderation"])


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
    "/{listing_id}/withdraw",
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
    return ModerationActionResponse(
        id=action.id,
        listing_id=action.listing_id,
        moderator_id=action.moderator_id,
        action_type=action.action_type,
        reason=action.reason,
        created_at=action.created_at,
    )
