"""Скарги на оголошення та їх розгляд адміністратором (FR-016)."""

from dataclasses import dataclass
from uuid import UUID

from src.domain.activity import ActivityType
from src.domain.complaints import (
    COMPLAINT_NOTE_MAX_LENGTH,
    Complaint,
    ComplaintReason,
    ComplaintStatus,
    normalize_complaint_text,
)
from src.domain.exceptions import (
    ComplaintConflictError,
    ComplaintNotFoundError,
    DuplicateComplaintError,
    InvalidComplaintError,
    ListingNotFoundError,
    ListingUnauthorizedError,
    ModerationForbiddenError,
)
from src.domain.listings import Listing, utc_now
from src.domain.users import CurrentUser, UserRole
from src.repositories.listings import ListingRepository
from src.repositories.support import ComplaintRepository
from src.repositories.users import UserRepository
from src.services.activity import ActivityLogService


@dataclass(frozen=True)
class ComplaintView:
    """Скарга зі зрозумілими адміністраторові назвою оголошення та автором."""

    complaint: Complaint
    listing_title: str | None
    listing_status: str | None
    reporter_email: str | None


class ComplaintService:
    """Подання скарг користувачами й розгляд адміністраторами."""

    def __init__(
        self,
        complaints: ComplaintRepository,
        listings: ListingRepository,
        users: UserRepository,
        activity: ActivityLogService,
    ) -> None:
        self._complaints = complaints
        self._listings = listings
        self._users = users
        self._activity = activity

    def submit(
        self,
        actor: CurrentUser | None,
        listing_id: UUID,
        reason: ComplaintReason,
        details: str = "",
    ) -> Complaint:
        """Створює скаргу на активне чуже оголошення; одна скарга на користувача."""
        if actor is None:
            raise ListingUnauthorizedError("Потрібна ідентифікація користувача")
        listing = self._listings.get(listing_id)
        if listing is None or not listing.is_public():
            raise ListingNotFoundError("Оголошення не знайдено")
        if listing.user_id == actor.user_id:
            raise InvalidComplaintError("Не можна скаржитися на власне оголошення")
        if self._complaints.find(listing_id, actor.user_id) is not None:
            raise DuplicateComplaintError("Ви вже скаржилися на це оголошення")
        complaint = self._complaints.add(
            Complaint(
                listing_id=listing_id,
                reporter_id=actor.user_id,
                reason=reason,
                details=details,
            )
        )
        self._activity.record(
            actor,
            ActivityType.COMPLAINT_SUBMITTED,
            listing_id,
            f"Причина: {reason.value}",
        )
        return complaint

    def list_complaints(
        self, admin: CurrentUser | None, status: ComplaintStatus | None = None
    ) -> list[ComplaintView]:
        """Скарги для адмін-панелі (нові першими, якщо фільтр не задано)."""
        self._require_admin(admin)
        items = self._complaints.list_all(status)
        items.sort(key=lambda item: item.status != ComplaintStatus.OPEN)
        return [self.view(item) for item in items]

    def resolve(
        self,
        admin: CurrentUser | None,
        complaint_id: UUID,
        status: ComplaintStatus,
        note: str = "",
    ) -> Complaint:
        """Позначає скаргу опрацьованою або відхиленою й пише подію в журнал."""
        admin = self._require_admin(admin)
        if status == ComplaintStatus.OPEN:
            raise InvalidComplaintError("Оберіть статус RESOLVED або DISMISSED")
        clean_note = normalize_complaint_text(
            note, COMPLAINT_NOTE_MAX_LENGTH, "Примітка"
        )
        complaint = self._complaints.get(complaint_id)
        if complaint is None:
            raise ComplaintNotFoundError("Скаргу не знайдено")
        if complaint.status != ComplaintStatus.OPEN:
            raise ComplaintConflictError("Скаргу вже розглянуто")
        complaint.status = status
        complaint.resolved_by = admin.user_id
        complaint.resolved_at = utc_now()
        complaint.resolution_note = clean_note
        saved = self._complaints.save(complaint)
        self._activity.record(
            admin,
            (
                ActivityType.COMPLAINT_RESOLVED
                if status == ComplaintStatus.RESOLVED
                else ActivityType.COMPLAINT_DISMISSED
            ),
            complaint.listing_id,
            clean_note,
        )
        return saved

    def view(self, complaint: Complaint) -> ComplaintView:
        listing: Listing | None = self._listings.get(complaint.listing_id)
        reporter = self._users.get_by_id(complaint.reporter_id)
        return ComplaintView(
            complaint=complaint,
            listing_title=listing.title if listing else None,
            listing_status=listing.status.value if listing else None,
            reporter_email=reporter.email if reporter else None,
        )

    @staticmethod
    def _require_admin(admin: CurrentUser | None) -> CurrentUser:
        if admin is None:
            raise ListingUnauthorizedError("Потрібна ідентифікація користувача")
        if admin.role != UserRole.ADMIN:
            raise ModerationForbiddenError("Дія дозволена лише адміністраторам")
        return admin
