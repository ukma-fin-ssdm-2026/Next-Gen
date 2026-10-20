"""Валідація університетської пошти (FR-001, SEC-001)."""

ALLOWED_DOMAIN = "ukma.edu.ua"


def _normalize(email: str) -> str:
    return email.strip().lower()


def is_ukma_email(email: str) -> bool:
    """Повертає True, якщо адреса належить домену @ukma.edu.ua."""
    return _normalize(email).endswith("@" + ALLOWED_DOMAIN)