"""Check recovery of committed listings in the disposable CI PostgreSQL service."""

import os
import re
import subprocess
import time
from uuid import uuid4

from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from src.api.main import app
from src.db.models import CategoryRow, ListingRow, UserRow


def main() -> None:
    container = os.environ["POSTGRES_SERVICE_ID"]
    if os.getenv("GITHUB_ACTIONS") != "true" or not re.fullmatch(
        r"[0-9a-f]{64}", container
    ):
        raise RuntimeError("Expected the disposable GitHub Actions service container")

    engine = create_engine(os.environ["DATABASE_URL"])
    with Session(engine) as session, session.begin():
        user = UserRow(
            tenant_id=uuid4(),
            entra_object_id=uuid4(),
            email=f"{uuid4()}@example.org",
            display_name="Recovery test",
        )
        category = CategoryRow(name="Recovery test", slug=f"test-{uuid4()}")
        session.add_all([user, category])
        session.flush()
        expected = {uuid4(): f"Recovery listing {i}" for i in range(3)}
        for listing_id, title in expected.items():
            session.add(
                ListingRow(
                    listing_id=listing_id,
                    user_id=user.user_id,
                    category_id=category.category_id,
                    title=title,
                    description="",
                    price=10,
                    contact="@recovery",
                )
            )
    engine.dispose()

    with TestClient(app) as client:

        def listings_available() -> bool:
            for listing_id, title in expected.items():
                response = client.get(f"/api/v1/listings/{listing_id}")
                if response.status_code == 503:
                    return False
                response.raise_for_status()
                listing = response.json()
                assert listing["id"] == str(listing_id) and listing["title"] == title
            return True

        assert (
            listings_available()
        ), "API must serve every committed listing before crash"
        start = time.monotonic()
        subprocess.run(["docker", "kill", container], check=True)
        subprocess.run(["docker", "start", container], check=True)
        while not listings_available():
            if time.monotonic() - start >= 300:
                raise TimeoutError("PostgreSQL recovery exceeded 300 seconds")
            time.sleep(1)
        elapsed = time.monotonic() - start
        assert elapsed <= 300
        print(
            f"REL-001: {len(expected)} committed listings recovered in {elapsed:.2f}s"
        )


if __name__ == "__main__":
    main()
