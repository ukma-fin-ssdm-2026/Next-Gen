"""HTTP-тести каталогу та контролів безпеки TM-02 / TM-05."""

from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from src.domain.listings import SEED_LISTING_ID, SEED_OWNER_ID


def test_health(client: TestClient) -> None:
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"


def test_public_list_omits_contact(client: TestClient) -> None:
    response = client.get("/api/v1/listings")
    assert response.status_code == 200
    payload = response.json()
    assert payload
    for item in payload:
        assert "contact" not in item
        assert item["status"] == "ACTIVE"


def test_public_detail_omits_contact(client: TestClient) -> None:
    response = client.get(f"/api/v1/listings/{SEED_LISTING_ID}")
    assert response.status_code == 200
    assert "contact" not in response.json()


def test_withdrawn_listing_not_in_catalog(client: TestClient) -> None:
    response = client.get("/api/v1/listings")
    ids = {item["id"] for item in response.json()}
    assert str(SEED_LISTING_ID) in ids
    assert "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee" not in ids


def test_search_query(client: TestClient) -> None:
    response = client.get("/api/v1/listings", params={"q": "худі"})
    assert response.status_code == 200
    assert len(response.json()) == 1


def test_create_without_actor_is_401(
    client: TestClient,
    listing_payload: dict[str, object],
) -> None:
    response = client.post(
        "/api/v1/listings",
        json=listing_payload,
    )
    assert response.status_code == 401


def test_patch_foreign_listing_is_403(client: TestClient) -> None:
    response = client.patch(
        f"/api/v1/listings/{SEED_LISTING_ID}",
        headers={"X-Actor-Id": str(uuid4())},
        json={"title": "Спроба зламати чуже оголошення"},
    )
    assert response.status_code == 403
    assert "contact" not in response.json() or "detail" in response.json()


def test_owner_patch_updates_title_and_hides_contact(client: TestClient) -> None:
    response = client.patch(
        f"/api/v1/listings/{SEED_LISTING_ID}",
        headers={"X-Actor-Id": str(SEED_OWNER_ID)},
        json={"title": "Худі НаУКМА, розмір M"},
    )
    assert response.status_code == 200
    body = response.json()
    assert "contact" not in body
    assert body["title"] == "Худі НаУКМА, розмір M"


def test_patch_with_explicit_null_is_422(client: TestClient) -> None:
    response = client.patch(
        f"/api/v1/listings/{SEED_LISTING_ID}",
        headers={"X-Actor-Id": str(SEED_OWNER_ID)},
        json={"title": None},
    )
    assert response.status_code == 422


def test_delete_marks_withdrawn_and_hides_from_public(client: TestClient) -> None:
    response = client.delete(
        f"/api/v1/listings/{SEED_LISTING_ID}",
        headers={"X-Actor-Id": str(SEED_OWNER_ID)},
    )
    assert response.status_code == 204

    # 404 on direct public retrieval
    get_res = client.get(f"/api/v1/listings/{SEED_LISTING_ID}")
    assert get_res.status_code == 404

    # Excluded from public catalog
    list_res = client.get("/api/v1/listings")
    ids = {item["id"] for item in list_res.json()}
    assert str(SEED_LISTING_ID) not in ids


def test_filter_by_price_range_api(client: TestClient) -> None:
    res = client.get(
        "/api/v1/listings", params={"min_price": 100.0, "max_price": 200.0}
    )
    assert res.status_code == 200
    assert len(res.json()) == 1

    res_empty = client.get("/api/v1/listings", params={"min_price": 200.0})
    assert res_empty.status_code == 200
    assert len(res_empty.json()) == 0


def test_catalog_accepts_oldest_sort_order(
    client: TestClient,
    listing_payload: dict[str, object],
) -> None:
    created = client.post(
        "/api/v1/listings",
        headers={"X-Actor-Id": str(SEED_OWNER_ID)},
        json=listing_payload,
    )
    assert created.status_code == 201

    response = client.get("/api/v1/listings", params={"sort": "oldest"})

    assert response.status_code == 200
    assert response.json()[0]["id"] == str(SEED_LISTING_ID)


@pytest.mark.parametrize(
    "params",
    [
        {"skip": -1},
        {"limit": 0},
        {"limit": 101},
        {"q": ""},
        {"min_price": -0.01},
        {"sort": "unsupported"},
    ],
)
def test_catalog_rejects_invalid_query_boundaries(
    client: TestClient,
    params: dict[str, object],
) -> None:
    response = client.get("/api/v1/listings", params=params)

    assert response.status_code == 422
