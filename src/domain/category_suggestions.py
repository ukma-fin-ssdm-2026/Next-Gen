"""Доменна сутність пропозиції нової категорії та правила валідації (FR-015, US-010)."""

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
import re
import unicodedata
from uuid import UUID, uuid4

from src.domain.exceptions import InvalidCategorySuggestionError
from src.domain.listings import utc_now

SUGGESTION_NAME_MIN_LENGTH = 2
SUGGESTION_NAME_MAX_LENGTH = 40
MAX_PENDING_SUGGESTIONS_PER_USER = 3

_CYRILLIC_TO_LATIN: dict[str, str] = {
    "а": "a",
    "б": "b",
    "в": "v",
    "г": "h",
    "ґ": "g",
    "д": "d",
    "е": "e",
    "є": "ye",
    "ж": "zh",
    "з": "z",
    "и": "y",
    "і": "i",
    "ї": "yi",
    "й": "y",
    "к": "k",
    "л": "l",
    "м": "m",
    "н": "n",
    "о": "o",
    "п": "p",
    "р": "r",
    "с": "s",
    "т": "t",
    "у": "u",
    "ф": "f",
    "х": "kh",
    "ц": "ts",
    "ч": "ch",
    "ш": "sh",
    "щ": "shch",
    "ь": "",
    "ю": "yu",
    "я": "ya",
    "ъ": "",
    "ы": "y",
    "э": "e",
}


class CategorySuggestionStatus(str, Enum):
    """Статуси розгляду пропозиції нової категорії (FR-015)."""

    PENDING = "PENDING"
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"


def normalize_suggestion_name(name: str) -> str:
    """Перевіряє та нормалізує назву категорії (2–40 символів, без керівних)."""
    if not isinstance(name, str):
        raise InvalidCategorySuggestionError("Назва категорії має бути рядком")
    if any(
        unicodedata.category(ch).startswith("C") or ord(ch) < 32 or ord(ch) == 127
        for ch in name
    ):
        raise InvalidCategorySuggestionError(
            "Назва категорії не може містити керівні символи"
        )
    cleaned = name.strip()
    if not (SUGGESTION_NAME_MIN_LENGTH <= len(cleaned) <= SUGGESTION_NAME_MAX_LENGTH):
        raise InvalidCategorySuggestionError(
            f"Назва категорії має містити від {SUGGESTION_NAME_MIN_LENGTH} "
            f"до {SUGGESTION_NAME_MAX_LENGTH} символів після обрізання пробілів"
        )
    return cleaned


def build_category_slug(name: str) -> str:
    """Генерує людинозрозумілий латинський slug із назви категорії."""
    lowered = name.strip().lower()
    transliterated = "".join(_CYRILLIC_TO_LATIN.get(ch, ch) for ch in lowered)
    slug = re.sub(r"[^a-z0-9]+", "-", transliterated).strip("-")
    if not slug:
        slug = f"category-{uuid4().hex[:8]}"
    return slug[:100]


@dataclass
class CategorySuggestion:
    """Пропозиція нової категорії від продавця (FR-015, US-010)."""

    name: str
    proposer_id: UUID
    suggestion_id: UUID = field(default_factory=uuid4)
    status: CategorySuggestionStatus = CategorySuggestionStatus.PENDING
    reason: str | None = None
    category_id: UUID | None = None
    reviewed_by: UUID | None = None
    created_at: datetime = field(default_factory=utc_now)
    reviewed_at: datetime | None = None

    @classmethod
    def create(
        cls,
        *,
        name: str,
        proposer_id: UUID,
        suggestion_id: UUID | None = None,
    ) -> "CategorySuggestion":
        """Створює валідовану пропозицію категорії у статусі PENDING."""
        clean_name = normalize_suggestion_name(name)
        return cls(
            suggestion_id=suggestion_id or uuid4(),
            name=clean_name,
            proposer_id=proposer_id,
            status=CategorySuggestionStatus.PENDING,
            created_at=utc_now(),
        )
