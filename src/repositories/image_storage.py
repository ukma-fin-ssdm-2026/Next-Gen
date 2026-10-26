"""Протокол та in-memory адаптер сховища зображень оголошень (FR-002)."""

from typing import Protocol
from uuid import UUID

from src.domain.exceptions import InvalidListingImageError
from src.domain.listings import ListingImage

MIN_IMAGES_PER_LISTING = 1
MAX_IMAGES_PER_LISTING = 10
ALLOWED_IMAGE_PREFIXES = ("https://", "/uploads/")


def validate_image_url(url: str) -> str:
    """Перевіряє та нормалізує URL або шлях до зображення оголошення."""
    normalized = url.strip()
    if not normalized:
        raise InvalidListingImageError("URL зображення не може бути порожнім")
    if " " in normalized or not normalized.startswith(ALLOWED_IMAGE_PREFIXES):
        raise InvalidListingImageError(
            "URL зображення має починатися з https:// або /uploads/"
        )
    return normalized


class ImageStorage(Protocol):
    """Контракт збереження та отримання фотографій оголошення (FR-002)."""

    def save_images(
        self, listing_id: UUID, image_urls: list[str]
    ) -> list[ListingImage]:
        """Валідує та зберігає список зображень для оголошення з display_order."""

    def get_images(self, listing_id: UUID) -> list[ListingImage]:
        """Повертає збережені зображення оголошення у порядку display_order."""


class InMemoryImageStorage:
    """In-memory реалізація ImageStorage для модульних та API-тестів."""

    def __init__(self) -> None:
        self._storage: dict[UUID, list[ListingImage]] = {}

    def save_images(
        self, listing_id: UUID, image_urls: list[str]
    ) -> list[ListingImage]:
        if len(image_urls) < MIN_IMAGES_PER_LISTING:
            raise InvalidListingImageError(
                "Оголошення має містити щонайменше одне зображення (FR-002)"
            )
        if len(image_urls) > MAX_IMAGES_PER_LISTING:
            raise InvalidListingImageError(
                f"Кількість зображень не може перевищувати {MAX_IMAGES_PER_LISTING}"
            )
        images = [
            ListingImage(
                listing_id=listing_id,
                image_url=validate_image_url(raw_url),
                display_order=index,
            )
            for index, raw_url in enumerate(image_urls)
        ]
        self._storage[listing_id] = list(images)
        return images

    def get_images(self, listing_id: UUID) -> list[ListingImage]:
        return list(self._storage.get(listing_id, []))
