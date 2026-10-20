"""Валідація університетської пошти (FR-001, SEC-001)."""

ALLOWED_DOMAIN = "ukma.edu.ua"


def is_ukma_email(email: str) -> bool:
    """Повертає True, якщо адреса належить домену @ukma.edu.ua."""
    return email.endswith("@" + ALLOWED_DOMAIN)