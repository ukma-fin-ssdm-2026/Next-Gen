"""Бенчмарк API каталогу через ASGITransport (PERF-003, TP-N02, SEC-002).

Браузерну вимогу PERF-001 перевіряє окремий тест TP-N03.
"""

import asyncio
import math
import statistics
import time
from uuid import uuid4
import httpx
import pytest

from src.api.main import app
from src.domain.listings import (
    Listing,
    ListingCondition,
    ListingImage,
    ListingStatus,
)
from src.repositories.favorites import InMemoryFavoriteRepository
from src.repositories.listings import InMemoryListingRepository
from src.services.listings import ListingService
from src.api.deps import get_listing_service

CONCURRENT_USERS = 50
BENCHMARK_ROUNDS = 3
WARMUP_REQUESTS = 3
CATALOG_PAGE_SIZE = 20
CATALOG_PATH = f"/api/v1/listings?limit={CATALOG_PAGE_SIZE}"


def _p95(durations: list[float]) -> float:
    """Return the same nearest-rank p95 used by the benchmark."""
    if not durations:
        raise ValueError("p95 requires at least one duration")
    ordered = sorted(durations)
    index = math.ceil(0.95 * len(ordered)) - 1
    return ordered[max(index, 0)]


def _representative_p95(round_p95s: list[float]) -> float:
    """Use the median round p95 so one noisy shared-runner sample is not decisive."""
    if not round_p95s:
        raise ValueError("representative p95 requires at least one round")
    return statistics.median(round_p95s)


def test_representative_p95_requires_most_rounds_to_meet_the_limit() -> None:
    """[TP-N02] [PERF-003] Один шумний раунд не змінює висновок тесту."""
    assert _p95([float(value) for value in range(1, 101)]) == 95.0
    assert _representative_p95([0.140, 0.360, 0.160]) == pytest.approx(0.160)
    assert _representative_p95([0.340, 0.150, 0.360]) == pytest.approx(0.340)


@pytest.fixture
def performance_dataset() -> None:
    """Генерує 500 активних оголошень для вимірювання PERF-003."""
    repo = InMemoryListingRepository()
    owner_id = uuid4()
    cat_id = uuid4()

    for i in range(500):
        listing = Listing(
            id=uuid4(),
            user_id=owner_id,
            title=f"Тестовий товар #{i:03d} Могилянка",
            description=(
                f"Детальний тестовий опис товару номер {i} "
                "для вимірювання швидкодії PERF-003"
            ),
            price=10.0 + (i % 100) * 5.0,
            category_id=cat_id,
            contact=f"contact_{i}@ukma.edu.ua",
            status=ListingStatus.ACTIVE,
            condition=ListingCondition.GOOD,
            images=[
                ListingImage(
                    image_url=f"https://images.naukma.edu.ua/item_{i}.jpg",
                    display_order=0,
                )
            ],
        )
        repo.add(listing)

    fav_repo = InMemoryFavoriteRepository()
    svc = ListingService(repo, favorites=fav_repo)

    app.dependency_overrides[get_listing_service] = lambda: svc

    try:
        yield
    finally:
        app.dependency_overrides.pop(get_listing_service, None)


@pytest.mark.performance
@pytest.mark.anyio
@pytest.mark.parametrize("anyio_backend", ["asyncio"])
async def test_nfr_perf_003_concurrent_catalog_api_under_500_listings(
    performance_dataset: None,
) -> None:
    """[TP-N02] [PERF-003] [SEC-002]
    50 одночасних запитів першої сторінки API на 500 активних оголошеннях.

    Критерії прийняття:
    - у кожному з трьох раундів 50 запитів виконуються конкурентно;
    - 0% помилок (status_code == 200 на кожному запиті);
    - медіана p95 трьох раундів <= 300 мс (0.300 с);
    - у жодній відповіді не розкрито контакти (SEC-002).
    """
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        # Кілька прогрівальних запитів прибирають cold-start із вимірювання.
        for _ in range(WARMUP_REQUESTS):
            warmup_res = await client.get(CATALOG_PATH)
            assert warmup_res.status_code == 200

        async def user_request(user_idx: int) -> dict:
            start = time.perf_counter()
            response = await client.get(CATALOG_PATH)
            elapsed = time.perf_counter() - start

            return {
                "user_idx": user_idx,
                "status_code": response.status_code,
                "elapsed": elapsed,
                "items": response.json() if response.status_code == 200 else [],
            }

        round_p95s: list[float] = []
        round_means: list[float] = []
        round_maxima: list[float] = []
        for _ in range(BENCHMARK_ROUNDS):
            # Одночасний конкурентний запуск 50 віртуальних клієнтів.
            tasks = [user_request(i) for i in range(CONCURRENT_USERS)]
            results = await asyncio.gather(*tasks)
            assert len(results) == CONCURRENT_USERS

            durations = [r["elapsed"] for r in results]
            round_p95s.append(_p95(durations))
            round_means.append(statistics.mean(durations))
            round_maxima.append(max(durations))

            # Верифікація відсутності помилок та контактних даних (SEC-002).
            for r in results:
                assert (
                    r["status_code"] == 200
                ), f"Помилка HTTP {r['status_code']} для користувача #{r['user_idx']}"
                assert len(r["items"]) == CATALOG_PAGE_SIZE
                for item in r["items"]:
                    assert (
                        "contact" not in item
                    ), "Дефект SEC-002: витік контактів продавця"

        representative_p95 = _representative_p95(round_p95s)

        print(
            f"\n[PERF-003 Concurrent Benchmark Report]\n"
            f"Simultaneous Users: {CONCURRENT_USERS} | Listings: 500 | "
            f"Rounds: {BENCHMARK_ROUNDS}\n"
            f"Round p95: {[round(value * 1000, 2) for value in round_p95s]} ms | "
            f"Median p95: {representative_p95*1000:.2f} ms | "
            f"Mean range: {min(round_means)*1000:.2f}–"
            f"{max(round_means)*1000:.2f} ms | "
            f"Max: {max(round_maxima)*1000:.2f} ms | "
            f"Error Rate: 0.0%"
        )

        # Більшість раундів має вкладатися у PERF-003.
        assert representative_p95 <= 0.300, (
            "Порушення PERF-003: медіана p95 = "
            f"{representative_p95*1000:.2f} мс > 300 мс; "
            f"раунди = {[round(value * 1000, 2) for value in round_p95s]} мс"
        )
