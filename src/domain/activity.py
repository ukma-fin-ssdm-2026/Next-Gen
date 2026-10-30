"""Журнал дій користувачів та адміністраторів (FR-018)."""

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from uuid import UUID, uuid4

from src.domain.listings import utc_now
from src.domain.users import UserRole

ACTIVITY_DETAILS_MAX_LENGTH = 300


class ActivityType(str, Enum):
    """Типи подій, які пишуться в журнал дій."""

    LISTING_CREATED = "LISTING_CREATED"
    LISTING_UPDATED = "LISTING_UPDATED"
    LISTING_WITHDRAWN = "LISTING_WITHDRAWN"
    FAVORITE_ADDED = "FAVORITE_ADDED"
    FAVORITE_REMOVED = "FAVORITE_REMOVED"
    COMPLAINT_SUBMITTED = "COMPLAINT_SUBMITTED"
    COMPLAINT_RESOLVED = "COMPLAINT_RESOLVED"
    COMPLAINT_DISMISSED = "COMPLAINT_DISMISSED"
    FEEDBACK_SUBMITTED = "FEEDBACK_SUBMITTED"
    FEEDBACK_RESOLVED = "FEEDBACK_RESOLVED"
    PROFILE_UPDATED = "PROFILE_UPDATED"


# Дії, які можуть виконувати лише адміністратори: вони потрапляють у журнал
# адміністраторів, усе інше (доступне кожному користувачу) — у журнал користувачів.
ADMIN_ONLY_ACTIVITY_TYPES = frozenset(
    {
        ActivityType.COMPLAINT_RESOLVED,
        ActivityType.COMPLAINT_DISMISSED,
        ActivityType.FEEDBACK_RESOLVED,
    }
)


@dataclass(frozen=True)
class ActivityEvent:
    """Незмінний запис: хто, з якою роллю, що зробив і над яким оголошенням."""

    actor_id: UUID
    actor_role: UserRole
    action_type: ActivityType
    listing_id: UUID | None = None
    details: str = ""
    id: UUID = field(default_factory=uuid4)
    created_at: datetime = field(default_factory=utc_now)

    def __post_init__(self) -> None:
        if len(self.details) > ACTIVITY_DETAILS_MAX_LENGTH:
            object.__setattr__(
                self, "details", self.details[:ACTIVITY_DETAILS_MAX_LENGTH]
            )
