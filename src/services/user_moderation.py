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
from src.domain.users import CurrentUser, User, UserRole
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

    def block_user_by_email(
        self, moderator: CurrentUser | None, email: str, reason: str
    ) -> ModerationAction:
        """Блокує користувача за email (лише для тих, хто вже входив на сайт)."""
        user_id = self._resolve_email(moderator, email)
        return self._set_blocked(moderator, user_id, reason, blocked=True)

    def unblock_user_by_email(
        self, moderator: CurrentUser | None, email: str, reason: str
    ) -> ModerationAction:
        """Розблоковує користувача за email."""
        user_id = self._resolve_email(moderator, email)
        return self._set_blocked(moderator, user_id, reason, blocked=False)

    def list_blocked(self, moderator: CurrentUser | None) -> list[User]:
        """Список заблокованих користувачів із причиною (лише для ADMIN)."""
        self._require_admin(moderator)
        return self._users.list_blocked()

    def _resolve_email(self, moderator: CurrentUser | None, email: str) -> UUID:
        """Спершу перевіряє права, щоб не-адміністратор не міг перебирати адреси."""
        self._require_admin(moderator)
        user = self._users.get_by_email(email)
        if user is None:
            raise UserNotFoundError(
                "Користувача з такою адресою не знайдено: він ще не входив на сайт"
            )
        return user.user_id

    @staticmethod
    def _require_admin(moderator: CurrentUser | None) -> CurrentUser:
        if moderator is None:
            raise ListingUnauthorizedError("Потрібна ідентифікація користувача")
        if moderator.role != UserRole.ADMIN:
            raise ModerationForbiddenError("Дія дозволена лише адміністраторам")
        return moderator

    def _set_blocked(
        self,
        moderator: CurrentUser | None,
        user_id: UUID,
        reason: str,
        *,
        blocked: bool,
    ) -> ModerationAction:
        moderator = self._require_admin(moderator)
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
            previous = (user.is_blocked, user.block_reason, user.blocked_at)
            user.is_blocked = blocked
            user.block_reason = action.reason if blocked else None
            user.blocked_at = action.created_at if blocked else None
            try:
                self._users.save(user)
                self._actions.add(action)
            except Exception:
                user.is_blocked, user.block_reason, user.blocked_at = previous
                self._users.save(user)
                raise
        if blocked:
            self._sessions.revoke_user(user_id)
        return action
