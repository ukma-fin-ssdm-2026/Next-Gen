"""Звернення до адміністрації та їх опрацювання (FR-017)."""

from dataclasses import dataclass
from uuid import UUID

from src.domain.activity import ActivityType
from src.domain.exceptions import (
    FeedbackConflictError,
    FeedbackNotFoundError,
    ListingUnauthorizedError,
    ModerationForbiddenError,
)
from src.domain.feedback import Feedback, FeedbackStatus
from src.domain.listings import utc_now
from src.domain.users import CurrentUser, UserRole
from src.repositories.support import FeedbackRepository
from src.repositories.users import UserRepository
from src.services.activity import ActivityLogService


@dataclass(frozen=True)
class FeedbackView:
    """Звернення з email автора для адмін-панелі."""

    feedback: Feedback
    user_email: str | None


class FeedbackService:
    """Подання звернень користувачами й опрацювання адміністраторами."""

    def __init__(
        self,
        feedback: FeedbackRepository,
        users: UserRepository,
        activity: ActivityLogService,
    ) -> None:
        self._feedback = feedback
        self._users = users
        self._activity = activity

    def submit(self, actor: CurrentUser | None, subject: str, message: str) -> Feedback:
        """Зберігає звернення автентифікованого користувача."""
        if actor is None:
            raise ListingUnauthorizedError("Потрібна ідентифікація користувача")
        item = self._feedback.add(
            Feedback(user_id=actor.user_id, subject=subject, message=message)
        )
        self._activity.record(
            actor, ActivityType.FEEDBACK_SUBMITTED, None, item.subject
        )
        return item

    def list_feedback(
        self, admin: CurrentUser | None, status: FeedbackStatus | None = None
    ) -> list[FeedbackView]:
        """Звернення для адмін-панелі: нові першими."""
        self._require_admin(admin)
        items = self._feedback.list_all(status)
        items.sort(key=lambda item: item.status != FeedbackStatus.NEW)
        views = []
        for item in items:
            author = self._users.get_by_id(item.user_id)
            views.append(FeedbackView(item, author.email if author else None))
        return views

    def resolve(self, admin: CurrentUser | None, feedback_id: UUID) -> Feedback:
        """Позначає звернення опрацьованим і пише подію в журнал."""
        admin = self._require_admin(admin)
        item = self._feedback.get(feedback_id)
        if item is None:
            raise FeedbackNotFoundError("Звернення не знайдено")
        if item.status != FeedbackStatus.NEW:
            raise FeedbackConflictError("Звернення вже опрацьовано")
        item.status = FeedbackStatus.RESOLVED
        item.resolved_by = admin.user_id
        item.resolved_at = utc_now()
        saved = self._feedback.save(item)
        self._activity.record(admin, ActivityType.FEEDBACK_RESOLVED, None, item.subject)
        return saved

    @staticmethod
    def _require_admin(admin: CurrentUser | None) -> CurrentUser:
        if admin is None:
            raise ListingUnauthorizedError("Потрібна ідентифікація користувача")
        if admin.role != UserRole.ADMIN:
            raise ModerationForbiddenError("Дія дозволена лише адміністраторам")
        return admin
