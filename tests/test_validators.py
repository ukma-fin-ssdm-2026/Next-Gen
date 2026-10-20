import pytest

from src.domain.validators import is_ukma_email


def test_accepts_ukma_email():
    assert is_ukma_email("student@ukma.edu.ua") is True


def test_rejects_other_domain():
    assert is_ukma_email("student@gmail.com") is False


def test_ignores_case_and_spaces():
    assert is_ukma_email("  Student@UKMA.edu.ua ") is True


@pytest.mark.parametrize(
    "email",
    [
        "@ukma.edu.ua",
        "a@b@ukma.edu.ua",
    ],
)
def test_rejects_malformed_email(email):
    assert is_ukma_email(email) is False