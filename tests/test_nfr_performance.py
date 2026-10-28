"""Виконуваний NFR-тест продуктивності (NFR Benchmark Bonus - 0,25 бала).

Перевіряє нефункціональну вимогу PERF-001 (Каталог оголошень) та сценарій TP-N02:
«Час завантаження списку з 500 активних оголошень — не більше 300 мс
при 50 запитах (95-й процентиль, p95 <= 300 мс), частка помилок 0%».
Також перевіряє супутню інваріантність безпеки SEC-002 (відсутність контактів).
"""

import statistics
import time
from uuid import uuid4
from fastapi.testclient import TestClient
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
import src.api.deps as deps


@pytest.fixture
def performance_client() -> TestClient:
    """Клієнт із 500 активними оголошеннями в репозиторії для вимірювання PERF-001."""
    repo = InMemoryListingRepository()
    owner_id = uuid4()
    cat_id = uuid4()

    # Генеруємо 500 активних оголошень з різними цінами та назвами
    for i in range(500):
        listing = Listing(
            id=uuid4(),
            user_id=owner_id,
            title=f"Тестовий товар #{i:03d} Могилянка",
            description=(f"Детальний опис товару номер {i} для тестування PERF-001"),
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

    # Підміняємо глобальний сервіс для ізольованого тесту
    original_svc = deps.listing_service
    deps.listing_service = svc

    client = TestClient(app)
    try:
        yield client
    finally:
        deps.listing_service = original_svc


def test_nfr_perf_001_catalog_latency_under_500_listings(
    performance_client: TestClient,
) -> None:
    """TP-N02 / PERF-001: 50 запитів до каталогу з 500 активними оголошеннями.

    Критерії прийняття:
    - 0% помилок (status_code == 200 на кожному запиті);
    - p95 часу відповіді <= 300 мс (0.300 с);
    - у жодній відповіді не розкрито контакти (SEC-002).
    """
    client = performance_client

    # Прогрів (warmup)
    warmup_res = client.get("/api/v1/listings?limit=20")
    assert warmup_res.status_code == 200

    durations: list[float] = []
    num_requests = 50

    for i in range(num_requests):
        # Варіюємо параметри запиту для реалістичності навантаження
        query_param = f"#{i:03d}" if i % 2 == 0 else "Могилянка"
        start = time.perf_counter()
        response = client.get(
            f"/api/v1/listings?limit=20&query={query_param}&sort=newest"
        )
        elapsed = time.perf_counter() - start

        durations.append(elapsed)

        # Перевірка результату запиту
        assert (
            response.status_code == 200
        ), f"Запит #{i} повернув помилку: {response.status_code}"
        items = response.json()
        assert isinstance(items, list)

        # Перевірка SEC-002 (жоден елемент не має контактів)
        for item in items:
            assert (
                "contact" not in item
            ), "Критичний дефект SEC-002: витік контакту продавця"

    # Розрахунок метрик
    durations.sort()
    # 95-й процентиль серед 50 вимірів
    p95_index = int(0.95 * len(durations)) - 1
    p95 = durations[p95_index]
    mean_latency = statistics.mean(durations)
    max_latency = max(durations)

    print(
        f"\n[PERF-001 Benchmark Report] Requests: {num_requests}, 500 listings\n"
        f"Mean: {mean_latency*1000:.2f} ms | "
        f"p95: {p95*1000:.2f} ms | "
        f"Max: {max_latency*1000:.2f} ms"
    )

    # Вимоги PERF-001: p95 <= 300 мс (0.300 с)
    assert p95 <= 0.300, f"Порушення PERF-001: p95 = {p95*1000:.2f} мс > 300 мс"
