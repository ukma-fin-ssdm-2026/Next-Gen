"""Скарги на повідомлення чату та їх розгляд адміністратором (ADR-005)."""

from dataclasses import dataclass
from uuid import UUID

from src.domain.complaints import normalize_complaint_text
from src.domain.exceptions import (
    ComplaintConflictError,
    ComplaintNotFoundError,
    ConversationNotFoundError,
    DuplicateComplaintError,
    InvalidComplaintError,
    ListingUnauthorizedError,
    ModerationForbiddenError,
)
from src.domain.listings import utc_now
from src.domain.message_reports import (
    MESSAGE_REPORT_NOTE_MAX_LENGTH,
    MessageReport,
    MessageReportReason,
    MessageReportStatus,
)
from src.domain.users import CurrentUser, UserRole
from src.repositories.conversations import ConversationRepository
from src.repositories.message_reports import MessageReportRepository
from src.repositories.users import UserRepository


@dataclass(frozen=True)
class MessageReportView:
    """Скарга зі зрозумілими адміністраторові іменами сторін."""

    report: MessageReport
    reporter_name: str | None
    reported_name: str | None


class MessageReportService:
    """Подання скарг на повідомлення учасниками розмови й розгляд адміністраторами."""

    def __init__(
        self,
        reports: MessageReportRepository,
        conversations: ConversationRepository,
        users: UserRepository,
    ) -> None:
        self._reports = reports
        self._conversations = conversations
        self._users = users

    def submit(
        self,
        actor: CurrentUser | None,
        conversation_id: UUID,
        message_id: UUID,
        reason: MessageReportReason,
        details: str = "",
    ) -> MessageReport:
        """Скарга на чуже повідомлення своєї розмови; одна від користувача.

        Не-учасник, вигадана розмова чи повідомлення дають однакову 404.
        """
        if actor is None:
            raise ListingUnauthorizedError("Потрібна ідентифікація користувача")
        conversation = self._conversations.get(conversation_id)
        if conversation is None or not conversation.has_participant(actor.user_id):
            raise ConversationNotFoundError("Повідомлення не знайдено")
        message = self._conversations.get_message(conversation_id, message_id)
        if message is None:
            raise ConversationNotFoundError("Повідомлення не знайдено")
        if message.sender_id == actor.user_id:
            raise InvalidComplaintError("Не можна скаржитися на власне повідомлення")
        if self._reports.find(message_id, actor.user_id) is not None:
            raise DuplicateComplaintError("Ви вже скаржилися на це повідомлення")
        return self._reports.add(
            MessageReport(
                message_id=message_id,
                conversation_id=conversation_id,
                reporter_id=actor.user_id,
                reported_user_id=message.sender_id,
                body_snapshot=message.body,
                reason=reason,
                details=details,
            )
        )

    def list_reports(
        self, admin: CurrentUser | None, status: MessageReportStatus | None = None
    ) -> list[MessageReportView]:
        """Скарги для адмін-панелі: відкриті першими."""
        self._require_admin(admin)
        items = self._reports.list_all(status)
        items.sort(key=lambda item: item.status != MessageReportStatus.OPEN)
        return [self.view(item) for item in items]

    def resolve(
        self,
        admin: CurrentUser | None,
        report_id: UUID,
        status: MessageReportStatus,
        note: str = "",
    ) -> MessageReport:
        """Позначає скаргу опрацьованою або відхиленою."""
        admin = self._require_admin(admin)
        if status == MessageReportStatus.OPEN:
            raise InvalidComplaintError("Оберіть статус RESOLVED або DISMISSED")
        clean_note = normalize_complaint_text(
            note, MESSAGE_REPORT_NOTE_MAX_LENGTH, "Примітка"
        )
        report = self._reports.get(report_id)
        if report is None:
            raise ComplaintNotFoundError("Скаргу не знайдено")
        if report.status != MessageReportStatus.OPEN:
            raise ComplaintConflictError("Скаргу вже розглянуто")
        report.status = status
        report.resolved_by = admin.user_id
        report.resolved_at = utc_now()
        report.resolution_note = clean_note
        return self._reports.save(report)

    def view(self, report: MessageReport) -> MessageReportView:
        reporter = self._users.get_by_id(report.reporter_id)
        reported = self._users.get_by_id(report.reported_user_id)
        return MessageReportView(
            report=report,
            reporter_name=reporter.display_name if reporter else None,
            reported_name=reported.display_name if reported else None,
        )

    @staticmethod
    def _require_admin(admin: CurrentUser | None) -> CurrentUser:
        if admin is None:
            raise ListingUnauthorizedError("Потрібна ідентифікація користувача")
        if admin.role != UserRole.ADMIN:
            raise ModerationForbiddenError("Дія дозволена лише адміністраторам")
        return admin
