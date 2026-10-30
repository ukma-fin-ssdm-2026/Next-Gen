"""Бенчмарк серверного компонента PERF-001 (TP-N02, SEC-002).

Перевіряє серверний компонент нефункціональної вимоги PERF-001 (Каталог оголошень)
та сценарій TP-N02 під конкурентним асинхронним навантаженням:
«Час завантаження списку з 500 активних оголошень — не більше 300 мс
при 50 одночасних користувачах (95-й процентиль, p95 <= 300 мс), частка помилок 0%».

Межі валідації:
- Тест перевіряє швидкодію бекенд-сервісу, фільтрації та роутерів через
  in-process ASGITransport з одночасним запуском 50 запитів (asyncio.gather).
- Повне наскрізне тестування PERF-001 (з урахуванням затримок мережі, СУБД PostgreSQL,
  Docker-інфраструктури та клієнтського рендерингу сторінки React) заплановано
  виконувати через інструменти навантаження (Locust/k6) у розгорнутому середовищі.
"""

import asyncio
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


@pytest.fixture
def performance_dataset() -> None:
    """Генерує 500 активних оголошень в репозиторії для вимірювання PERF-001."""
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
                "для вимірювання швидкодії PERF-001"
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


@pytest.mark.anyio
async def test_nfr_perf_001_concurrent_catalog_latency_under_500_listings(
    performance_dataset: None,
) -> None:
    """[TP-N02] [PERF-001] [SEC-002]
    50 одночасних користувачів до каталогу з 500 оголошеннями.

    Критерії прийняття:
    - 50 запитів виконуються конкурентно (asyncio.gather);
    - 0% помилок (status_code == 200 на кожному запиті);
    - p95 часу відповіді <= 300 мс (0.300 с);
    - у жодній відповіді не розкрито контакти (SEC-002).
    """
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        # Прогрів (warmup)
        warmup_res = await client.get("/api/v1/listings?limit=20")
        assert warmup_res.status_code == 200

        async def user_request(user_idx: int) -> dict:
            query_param = f"#{user_idx:03d}" if user_idx % 2 == 0 else "Могилянка"
            url = f"/api/v1/listings?limit=20&query={query_param}&sort=newest"

            start = time.perf_counter()
            response = await client.get(url)
            elapsed = time.perf_counter() - start

            return {
                "user_idx": user_idx,
                "status_code": response.status_code,
                "elapsed": elapsed,
                "items": response.json() if response.status_code == 200 else [],
            }

        # Одночасний конкурентний запуск 50 віртуальних клієнтів
        tasks = [user_request(i) for i in range(CONCURRENT_USERS)]
        results = await asyncio.gather(*tasks)

        assert len(results) == CONCURRENT_USERS

        durations = [r["elapsed"] for r in results]
        durations.sort()

        # 95-й процентиль серед 50 конкурентних запитів
        p95_index = int(0.95 * len(durations)) - 1
        p95 = durations[p95_index]
        mean_latency = statistics.mean(durations)
        max_latency = max(durations)

        # Верифікація відсутності помилок та контактних даних (SEC-002)
        for r in results:
            assert (
                r["status_code"] == 200
            ), f"Помилка HTTP {r['status_code']} для користувача #{r['user_idx']}"
            for item in r["items"]:
                assert "contact" not in item, "Дефект SEC-002: витік контактів продавця"

        print(
            f"\n[PERF-001 Concurrent Benchmark Report]\n"
            f"Simultaneous Users: {CONCURRENT_USERS} | Listings: 500\n"
            f"Mean: {mean_latency*1000:.2f} ms | "
            f"p95: {p95*1000:.2f} ms | "
            f"Max: {max_latency*1000:.2f} ms | "
            f"Error Rate: 0.0%"
        )

        # Поріг вимоги PERF-001: p95 <= 300 мс (0.300 с)
        assert p95 <= 0.300, f"Порушення PERF-001: p95 = {p95*1000:.2f} мс > 300 мс"
