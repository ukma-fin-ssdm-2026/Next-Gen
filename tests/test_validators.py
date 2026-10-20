from src.domain.validators import is_ukma_email


def test_accepts_ukma_email():
    assert is_ukma_email("student@ukma.edu.ua") is True


def test_rejects_other_domain():
    assert is_ukma_email("student@gmail.com") is False