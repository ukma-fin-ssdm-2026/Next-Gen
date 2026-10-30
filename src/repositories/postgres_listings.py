"""PostgreSQL-адаптер репозиторію оголошень з транзакційним збереженням зображень."""

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from src.db.converters import (
    image_domain_to_row,
    listing_domain_to_row,
    listing_row_to_domain,
)
from src.db.models import ListingImageRow, ListingRow
from src.domain.listings import Listing


class PostgresListingRepository:
    """Реалізує ListingRepository.Protocol.

    Оголошення та пов'язані ListingImage зберігаються в одній транзакції (ADR-002).
    Зняття оголошення з публікації не видаляє його фізично — лише змінює статус.
    """

    def __init__(self, session: Session) -> None:
        self._session = session

    def list_all(self) -> list[Listing]:
        stmt = select(ListingRow).order_by(ListingRow.created_at.desc())
        rows = self._session.execute(stmt).scalars().all()
        return [listing_row_to_domain(r) for r in rows]

    def list_by_owner(self, user_id: UUID) -> list[Listing]:
        stmt = (
            select(ListingRow)
            .where(ListingRow.user_id == user_id)
            .order_by(ListingRow.created_at.desc())
        )
        rows = self._session.execute(stmt).scalars().all()
        return [listing_row_to_domain(r) for r in rows]

    def get(self, listing_id: UUID) -> Listing | None:
        row = self._session.get(ListingRow, listing_id)
        return listing_row_to_domain(row) if row else None

    def add(self, listing: Listing) -> Listing:
        """Зберігає оголошення і його зображення в одній транзакції."""
        row = listing_domain_to_row(listing)
        self._session.add(row)
        self._session.flush()  # отримуємо listing_id для FK

        for img in listing.images:
            img_row = image_domain_to_row(img)
            img_row.listing_id = row.listing_id
            self._session.add(img_row)

        self._session.flush()
        # Перезавантажуємо щоб selectinload зображень спрацював
        self._session.refresh(row)
        return listing_row_to_domain(row)

    def save(self, listing: Listing) -> Listing:
        """Оновлює оголошення та синхронізує зображення в одній транзакції."""
        existing = self._session.get(ListingRow, listing.id)
        if existing is None:
            return self.add(listing)

        row = listing_domain_to_row(listing, existing)

        # Синхронізація зображень
        existing_image_ids = {img.image_id for img in existing.images}
        new_image_ids = {img.image_id for img in listing.images}

        # Видаляємо зображення, яких немає в новому списку
        for img_row in list(existing.images):
            if img_row.image_id not in new_image_ids:
                self._session.delete(img_row)

        # Оновлюємо або додаємо зображення
        for img in listing.images:
            if img.image_id in existing_image_ids:
                existing_img = self._session.get(ListingImageRow, img.image_id)
                if existing_img:
                    image_domain_to_row(img, existing_img)
            else:
                img_row = image_domain_to_row(img)
                img_row.listing_id = row.listing_id
                self._session.add(img_row)

        self._session.flush()
        self._session.refresh(row)
        return listing_row_to_domain(row)

    def delete(self, listing_id: UUID) -> bool:
        """Видаляє оголошення фізично. Для м'якого видалення використовуйте save()."""
        row = self._session.get(ListingRow, listing_id)
        if row is None:
            return False
        self._session.delete(row)
        self._session.flush()
        return True
