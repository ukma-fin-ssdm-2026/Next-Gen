"""Журнал дій користувачів та адміністраторів (FR-018)."""

from dataclasses import dataclass
from datetime import datetime
from uuid import UUID

from src.domain.activity import ActivityEvent, ActivityType
from src.domain.exceptions import ListingUnauthorizedError, ModerationForbiddenError
from src.domain.users import CurrentUser, UserRole
from src.repositories.moderation import ModerationActionRepository
from src.repositories.support import ActivityRepository
from src.repositories.users import UserRepository


@dataclass(frozen=True)
class LogEntry:
    """Рядок журналу для адмін-панелі: хто, що, над чим і коли."""

    id: UUID
    created_at: datetime
    actor_id: UUID
    actor_email: str | None
    action_type: str
    listing_id: UUID | None
    target_user_id: UUID | None
    target_email: str | None
    details: str


class ActivityLogService:
    """Запис подій і читання журналів (лише для адміністраторів)."""

    def __init__(
        self,
        events: ActivityRepository,
        users: UserRepository,
        moderation: ModerationActionRepository,
    ) -> None:
        self._events = events
        self._users = users
        self._moderation = moderation

    def record(
        self,
        actor: CurrentUser,
        action_type: ActivityType,
        listing_id: UUID | None = None,
        details: str = "",
    ) -> ActivityEvent:
        """Додає незмінний запис про дію автентифікованого користувача."""
        return self._events.add(
            ActivityEvent(
                actor_id=actor.user_id,
                actor_role=actor.role,
                action_type=action_type,
                listing_id=listing_id,
                details=details,
            )
        )

    def user_log(
        self, admin: CurrentUser | None, skip: int = 0, limit: int = 100
    ) -> list[LogEntry]:
        """Дії звичайних користувачів від найновіших."""
        self._require_admin(admin)
        events = self._events.list_by_role(UserRole.USER, skip, limit)
        return [self._event_entry(event) for event in events]

    def admin_log(
        self, admin: CurrentUser | None, skip: int = 0, limit: int = 100
    ) -> list[LogEntry]:
        """Дії адміністраторів: журнал модерації разом із подіями адмінів."""
        self._require_admin(admin)
        entries = [
            self._event_entry(event)
            for event in self._events.list_by_role(UserRole.ADMIN, 0, skip + limit)
        ]
        for action in self._moderation.list_all():
            entries.append(
                LogEntry(
                    id=action.id,
                    created_at=action.created_at,
                    actor_id=action.moderator_id,
                    actor_email=self._email(action.moderator_id),
                    action_type=action.action_type.value,
                    listing_id=action.listing_id,
                    target_user_id=action.target_user_id,
                    target_email=self._email(action.target_user_id),
                    details=action.reason,
                )
            )
        entries.sort(key=lambda entry: entry.created_at, reverse=True)
        return entries[skip : skip + limit]

    def _event_entry(self, event: ActivityEvent) -> LogEntry:
        return LogEntry(
            id=event.id,
            created_at=event.created_at,
            actor_id=event.actor_id,
            actor_email=self._email(event.actor_id),
            action_type=event.action_type.value,
            listing_id=event.listing_id,
            target_user_id=None,
            target_email=None,
            details=event.details,
        )

    def _email(self, user_id: UUID | None) -> str | None:
        if user_id is None:
            return None
        user = self._users.get_by_id(user_id)
        return user.email if user else None

    @staticmethod
    def _require_admin(admin: CurrentUser | None) -> CurrentUser:
        if admin is None:
            raise ListingUnauthorizedError("Потрібна ідентифікація користувача")
        if admin.role != UserRole.ADMIN:
            raise ModerationForbiddenError("Дія дозволена лише адміністраторам")
        return admin
