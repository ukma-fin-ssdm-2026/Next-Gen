"""PostgreSQL-адаптери скарг, звернень і журналу дій (FR-016, FR-017, FR-018)."""

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from src.db.converters import (
    activity_domain_to_row,
    activity_row_to_domain,
    complaint_domain_to_row,
    complaint_row_to_domain,
    feedback_domain_to_row,
    feedback_row_to_domain,
)
from src.db.models import ActivityEventRow, ComplaintRow, FeedbackRow
from src.domain.activity import ActivityEvent
from src.domain.complaints import Complaint, ComplaintStatus
from src.domain.feedback import Feedback, FeedbackStatus
from src.domain.users import UserRole


class PostgresComplaintRepository:
    """Реалізує ComplaintRepository у PostgreSQL."""

    def __init__(self, session: Session) -> None:
        self._session = session

    def add(self, complaint: Complaint) -> Complaint:
        row = complaint_domain_to_row(complaint)
        self._session.add(row)
        self._session.flush()
        return complaint_row_to_domain(row)

    def get(self, complaint_id: UUID) -> Complaint | None:
        row = self._session.get(ComplaintRow, complaint_id)
        return complaint_row_to_domain(row) if row else None

    def save(self, complaint: Complaint) -> Complaint:
        existing = self._session.get(ComplaintRow, complaint.id)
        row = complaint_domain_to_row(complaint, existing)
        if existing is None:
            self._session.add(row)
        self._session.flush()
        return complaint_row_to_domain(row)

    def find(self, listing_id: UUID, reporter_id: UUID) -> Complaint | None:
        stmt = select(ComplaintRow).where(
            ComplaintRow.listing_id == listing_id,
            ComplaintRow.reporter_id == reporter_id,
        )
        row = self._session.execute(stmt).scalar_one_or_none()
        return complaint_row_to_domain(row) if row else None

    def list_all(self, status: ComplaintStatus | None = None) -> list[Complaint]:
        stmt = select(ComplaintRow).order_by(ComplaintRow.created_at.desc())
        if status is not None:
            stmt = stmt.where(ComplaintRow.status == status.value)
        return [
            complaint_row_to_domain(r) for r in self._session.execute(stmt).scalars()
        ]


class PostgresFeedbackRepository:
    """Реалізує FeedbackRepository у PostgreSQL."""

    def __init__(self, session: Session) -> None:
        self._session = session

    def add(self, feedback: Feedback) -> Feedback:
        row = feedback_domain_to_row(feedback)
        self._session.add(row)
        self._session.flush()
        return feedback_row_to_domain(row)

    def get(self, feedback_id: UUID) -> Feedback | None:
        row = self._session.get(FeedbackRow, feedback_id)
        return feedback_row_to_domain(row) if row else None

    def save(self, feedback: Feedback) -> Feedback:
        existing = self._session.get(FeedbackRow, feedback.id)
        row = feedback_domain_to_row(feedback, existing)
        if existing is None:
            self._session.add(row)
        self._session.flush()
        return feedback_row_to_domain(row)

    def list_all(self, status: FeedbackStatus | None = None) -> list[Feedback]:
        stmt = select(FeedbackRow).order_by(FeedbackRow.created_at.desc())
        if status is not None:
            stmt = stmt.where(FeedbackRow.status == status.value)
        return [
            feedback_row_to_domain(r) for r in self._session.execute(stmt).scalars()
        ]


class PostgresActivityRepository:
    """Реалізує ActivityRepository у PostgreSQL (лише INSERT і SELECT)."""

    def __init__(self, session: Session) -> None:
        self._session = session

    def add(self, event: ActivityEvent) -> ActivityEvent:
        row = activity_domain_to_row(event)
        self._session.add(row)
        self._session.flush()
        return activity_row_to_domain(row)

    def list_by_role(
        self, role: UserRole, skip: int = 0, limit: int = 100
    ) -> list[ActivityEvent]:
        stmt = (
            select(ActivityEventRow)
            .where(ActivityEventRow.actor_role == role.value)
            .order_by(ActivityEventRow.created_at.desc())
            .offset(skip)
            .limit(limit)
        )
        return [
            activity_row_to_domain(r) for r in self._session.execute(stmt).scalars()
        ]
