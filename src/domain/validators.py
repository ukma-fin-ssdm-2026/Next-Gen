"""Валідація університетської пошти (FR-001, SEC-001)."""


def is_ukma_email(email: str) -> bool:
    """Повертає True, якщо адреса належить домену @ukma.edu.ua."""
    return email.endswith("@ukma.edu.ua")