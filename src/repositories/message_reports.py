"""Сховища скарг на повідомлення: in-memory і PostgreSQL."""

from typing import Protocol
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from src.db.converters import (
    message_report_domain_to_row,
    message_report_row_to_domain,
)
from src.db.models import MessageReportRow
from src.domain.message_reports import MessageReport, MessageReportStatus


class MessageReportRepository(Protocol):
    """Контракт сховища скарг на повідомлення."""

    def add(self, report: MessageReport) -> MessageReport: ...

    def get(self, report_id: UUID) -> MessageReport | None: ...

    def save(self, report: MessageReport) -> MessageReport: ...

    def find(self, message_id: UUID, reporter_id: UUID) -> MessageReport | None: ...

    def list_all(
        self, status: MessageReportStatus | None = None
    ) -> list[MessageReport]: ...


class InMemoryMessageReportRepository:
    """Скарги в пам'яті процесу (без DATABASE_URL і для тестів)."""

    def __init__(self) -> None:
        self._items: dict[UUID, MessageReport] = {}

    def add(self, report: MessageReport) -> MessageReport:
        self._items[report.id] = report
        return report

    def get(self, report_id: UUID) -> MessageReport | None:
        return self._items.get(report_id)

    def save(self, report: MessageReport) -> MessageReport:
        self._items[report.id] = report
        return report

    def find(self, message_id: UUID, reporter_id: UUID) -> MessageReport | None:
        for item in self._items.values():
            if item.message_id == message_id and item.reporter_id == reporter_id:
                return item
        return None

    def list_all(
        self, status: MessageReportStatus | None = None
    ) -> list[MessageReport]:
        items = [i for i in self._items.values() if status in (None, i.status)]
        return sorted(items, key=lambda item: item.created_at, reverse=True)


class PostgresMessageReportRepository:
    """Реалізує MessageReportRepository у PostgreSQL."""

    def __init__(self, session: Session) -> None:
        self._session = session

    def add(self, report: MessageReport) -> MessageReport:
        row = message_report_domain_to_row(report)
        self._session.add(row)
        self._session.flush()
        return message_report_row_to_domain(row)

    def get(self, report_id: UUID) -> MessageReport | None:
        row = self._session.get(MessageReportRow, report_id)
        return message_report_row_to_domain(row) if row else None

    def save(self, report: MessageReport) -> MessageReport:
        existing = self._session.get(MessageReportRow, report.id)
        row = message_report_domain_to_row(report, existing)
        if existing is None:
            self._session.add(row)
        self._session.flush()
        return message_report_row_to_domain(row)

    def find(self, message_id: UUID, reporter_id: UUID) -> MessageReport | None:
        stmt = select(MessageReportRow).where(
            MessageReportRow.message_id == message_id,
            MessageReportRow.reporter_id == reporter_id,
        )
        row = self._session.execute(stmt).scalar_one_or_none()
        return message_report_row_to_domain(row) if row else None

    def list_all(
        self, status: MessageReportStatus | None = None
    ) -> list[MessageReport]:
        stmt = select(MessageReportRow).order_by(MessageReportRow.created_at.desc())
        if status is not None:
            stmt = stmt.where(MessageReportRow.status == status.value)
        return [
            message_report_row_to_domain(r)
            for r in self._session.execute(stmt).scalars()
        ]
