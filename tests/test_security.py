from fastapi.testclient import TestClient

from src.api.main import app

client = TestClient(app)

LISTING_ID = "3fa85f64-5717-4562-b3fc-2c963f66afa6"


def test_get_listing_hides_contact():
    """[TP-N01] [SEC-002] [FR-010]
    TM-05 / SEC-002: публічний GET не повертає контакт продавця.
    """
    response = client.get(f"/api/v1/listings/{LISTING_ID}")
    assert response.status_code == 200
    assert "contact" not in response.json()


def test_patch_listing_does_not_leak_contact():
    """[TP-N01] [SEC-002] [FR-010]
    TM-05 / SEC-002: PATCH без автентифікації не повертає контакт продавця.
    """
    response = client.patch(f"/api/v1/listings/{LISTING_ID}", json={})
    # Анонімний запит повертає 401 (TM-02) або 200 без контактів (TM-05)
    assert response.status_code in (200, 401)
    assert "contact" not in response.json()
