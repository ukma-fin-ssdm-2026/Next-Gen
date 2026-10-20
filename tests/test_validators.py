import pytest

from src.domain.validators import is_ukma_email


@pytest.mark.parametrize(
    "email",
    [
        "student@ukma.edu.ua",
        "  Student@UKMA.edu.ua ",
    ],
)
def test_accepts_ukma_email(email):
    assert is_ukma_email(email) is True


@pytest.mark.parametrize(
    "email",
    [
        "student@gmail.com",
        "@ukma.edu.ua",
        "a@b@ukma.edu.ua",
    ],
)
def test_rejects_invalid_email(email):
    assert is_ukma_email(email) is False
