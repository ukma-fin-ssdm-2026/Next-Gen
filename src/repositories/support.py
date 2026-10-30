"""Сховища скарг, звернень і журналу дій (FR-016, FR-017, FR-018)."""

from typing import Protocol
from uuid import UUID

from src.domain.activity import ADMIN_ONLY_ACTIVITY_TYPES, ActivityEvent
from src.domain.complaints import Complaint, ComplaintStatus
from src.domain.feedback import Feedback, FeedbackStatus


class ComplaintRepository(Protocol):
    """Контракт сховища скарг на оголошення."""

    def add(self, complaint: Complaint) -> Complaint: ...

    def get(self, complaint_id: UUID) -> Complaint | None: ...

    def save(self, complaint: Complaint) -> Complaint: ...

    def find(self, listing_id: UUID, reporter_id: UUID) -> Complaint | None: ...

    def list_all(self, status: ComplaintStatus | None = None) -> list[Complaint]: ...


class FeedbackRepository(Protocol):
    """Контракт сховища звернень до адміністрації."""

    def add(self, feedback: Feedback) -> Feedback: ...

    def get(self, feedback_id: UUID) -> Feedback | None: ...

    def save(self, feedback: Feedback) -> Feedback: ...

    def list_all(self, status: FeedbackStatus | None = None) -> list[Feedback]: ...


class ActivityRepository(Protocol):
    """Контракт append-only сховища журналу дій."""

    def add(self, event: ActivityEvent) -> ActivityEvent: ...

    def list_events(
        self, admin_only: bool, skip: int = 0, limit: int = 100
    ) -> list[ActivityEvent]: ...


class InMemoryComplaintRepository:
    """Скарги в пам'яті процесу (без DATABASE_URL і для тестів)."""

    def __init__(self) -> None:
        self._items: dict[UUID, Complaint] = {}

    def add(self, complaint: Complaint) -> Complaint:
        self._items[complaint.id] = complaint
        return complaint

    def get(self, complaint_id: UUID) -> Complaint | None:
        return self._items.get(complaint_id)

    def save(self, complaint: Complaint) -> Complaint:
        self._items[complaint.id] = complaint
        return complaint

    def find(self, listing_id: UUID, reporter_id: UUID) -> Complaint | None:
        for item in self._items.values():
            if item.listing_id == listing_id and item.reporter_id == reporter_id:
                return item
        return None

    def list_all(self, status: ComplaintStatus | None = None) -> list[Complaint]:
        items = [i for i in self._items.values() if status in (None, i.status)]
        return sorted(items, key=lambda item: item.created_at, reverse=True)


class InMemoryFeedbackRepository:
    """Звернення в пам'яті процесу (без DATABASE_URL і для тестів)."""

    def __init__(self) -> None:
        self._items: dict[UUID, Feedback] = {}

    def add(self, feedback: Feedback) -> Feedback:
        self._items[feedback.id] = feedback
        return feedback

    def get(self, feedback_id: UUID) -> Feedback | None:
        return self._items.get(feedback_id)

    def save(self, feedback: Feedback) -> Feedback:
        self._items[feedback.id] = feedback
        return feedback

    def list_all(self, status: FeedbackStatus | None = None) -> list[Feedback]:
        items = [i for i in self._items.values() if status in (None, i.status)]
        return sorted(items, key=lambda item: item.created_at, reverse=True)


class InMemoryActivityRepository:
    """Журнал дій у пам'яті процесу (без DATABASE_URL і для тестів)."""

    def __init__(self) -> None:
        self._items: list[ActivityEvent] = []

    def add(self, event: ActivityEvent) -> ActivityEvent:
        self._items.append(event)
        return event

    def list_events(
        self, admin_only: bool, skip: int = 0, limit: int = 100
    ) -> list[ActivityEvent]:
        items = [
            item
            for item in self._items
            if (item.action_type in ADMIN_ONLY_ACTIVITY_TYPES) == admin_only
        ]
        items.sort(key=lambda item: item.created_at, reverse=True)
        return items[skip : skip + limit]
