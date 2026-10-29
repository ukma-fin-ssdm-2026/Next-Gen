"""User Moderation Service: блокування й розблокування користувачів (FR-013)."""

from threading import Lock
from uuid import UUID

from src.domain.exceptions import (
    InvalidUserModerationError,
    ListingUnauthorizedError,
    ModerationForbiddenError,
    UserNotFoundError,
)
from src.domain.moderation import (
    ModerationAction,
    ModerationActionType,
    normalize_moderation_reason,
)
from src.domain.users import CurrentUser, UserRole
from src.repositories.moderation import ModerationActionRepository
from src.repositories.users import UserRepository
from src.services.auth_sessions import InMemoryAuthSessionStore


class UserModerationService:
    """Адміністративне блокування облікових записів незалежно від HTTP."""

    def __init__(
        self,
        users: UserRepository,
        actions: ModerationActionRepository,
        sessions: InMemoryAuthSessionStore,
    ) -> None:
        self._users = users
        self._actions = actions
        self._sessions = sessions
        # Серіалізує перевірку стану й зміну; з PostgreSQL це замінюється
        # транзакцією з SELECT ... FOR UPDATE.
        self._lock = Lock()

    def block_user(
        self, moderator: CurrentUser | None, user_id: UUID, reason: str
    ) -> ModerationAction:
        """Блокує користувача, відкликає його сесії й фіксує дію в журналі."""
        return self._set_blocked(moderator, user_id, reason, blocked=True)

    def unblock_user(
        self, moderator: CurrentUser | None, user_id: UUID, reason: str
    ) -> ModerationAction:
        """Розблоковує користувача й фіксує дію в журналі."""
        return self._set_blocked(moderator, user_id, reason, blocked=False)

    def _set_blocked(
        self,
        moderator: CurrentUser | None,
        user_id: UUID,
        reason: str,
        *,
        blocked: bool,
    ) -> ModerationAction:
        if moderator is None:
            raise ListingUnauthorizedError("Потрібна ідентифікація користувача")
        if moderator.role != UserRole.ADMIN:
            raise ModerationForbiddenError("Дія дозволена лише адміністраторам")
        action = ModerationAction(
            moderator_id=moderator.user_id,
            action_type=(
                ModerationActionType.BLOCK_USER
                if blocked
                else ModerationActionType.UNBLOCK_USER
            ),
            reason=normalize_moderation_reason(reason),
            target_user_id=user_id,
        )
        with self._lock:
            user = self._users.get_by_id(user_id)
            if user is None:
                raise UserNotFoundError("Користувача не знайдено")
            if blocked and user.user_id == moderator.user_id:
                raise InvalidUserModerationError("Не можна заблокувати себе")
            if blocked and user.role == UserRole.ADMIN:
                raise InvalidUserModerationError("Не можна заблокувати адміністратора")
            if user.is_blocked == blocked:
                raise InvalidUserModerationError(
                    "Користувача вже заблоковано"
                    if blocked
                    else "Користувача не заблоковано"
                )
            user.is_blocked = blocked
            try:
                self._users.save(user)
                self._actions.add(action)
            except Exception:
                user.is_blocked = not blocked
                self._users.save(user)
                raise
        if blocked:
            self._sessions.revoke_user(user_id)
        return action
