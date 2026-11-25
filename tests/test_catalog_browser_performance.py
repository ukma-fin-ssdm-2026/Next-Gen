"""Opt-in staging benchmark for the rendered public catalogue."""

import asyncio
import os

import pytest

from tests.test_nfr_performance import (
    CATALOG_PAGE_SIZE,
    CONCURRENT_USERS,
    WARMUP_REQUESTS,
    _p95,
)

CATALOG_READY_SCRIPT = """
(() => {
    const cardsAreLaidOut = () => {
        const cards = document.querySelectorAll(".catalog-page article.listing-card");
        return cards.length === __EXPECTED_CARDS__ &&
            [...cards].every(card => card.getClientRects().length);
    };
    const measure = () => {
        if (cardsAreLaidOut()) {
            requestAnimationFrame(() => {
                if (cardsAreLaidOut()) window.__catalogReadyMs = performance.now();
                else requestAnimationFrame(measure);
            });
        } else {
            requestAnimationFrame(measure);
        }
    };
    requestAnimationFrame(measure);
})();
"""


CATALOG_PHASES_SCRIPT = """
() => {
    const ready = window.__catalogReadyMs;
    const api = performance.getEntriesByType("resource").find(entry =>
        entry.initiatorType === "fetch" &&
        new URL(entry.name).pathname === "/api/v1/listings" &&
        entry.responseEnd > 0 && entry.responseEnd <= ready
    );
    if (!api) return null;
    return {
        before_api: api.startTime,
        api_request: api.responseEnd - api.startTime,
        after_api: ready - api.responseEnd
    };
}
"""


async def _measure_navigation(page, url: str) -> float:
    await page.add_init_script(
        CATALOG_READY_SCRIPT.replace("__EXPECTED_CARDS__", str(CATALOG_PAGE_SIZE))
    )
    response = await page.goto(url, wait_until="commit")
    assert response is not None and response.status == 200
    ready = await page.wait_for_function("() => window.__catalogReadyMs")
    measured_ms = await ready.json_value()
    assert type(measured_ms) in (int, float) and measured_ms > 0
    return float(measured_ms)


@pytest.mark.performance
def test_perf_001_catalog_renders_first_page_in_browser() -> None:
    """[TP-N03] [PERF-001] 50 одночасних відкриттів каталогу на staging."""
    base_url = os.getenv("CATALOG_STAGING_URL", "").strip().rstrip("/")
    if not base_url:
        pytest.skip("Set CATALOG_STAGING_URL to a dedicated staging environment")

    from playwright.async_api import async_playwright

    async def run() -> list[float]:
        async with async_playwright() as playwright:
            request = await playwright.request.new_context()
            try:
                readiness = await request.get(f"{base_url}/health/ready")
                assert (
                    readiness.ok and (await readiness.json())["database"] == "ok"
                ), "PERF-001 requires a ready PostgreSQL database"
                response = await request.get(f"{base_url}/api/v1/listings?limit=1")
                assert (
                    response.ok and response.headers.get("x-total-count") == "500"
                ), "PERF-001 requires exactly 500 active listings"
            finally:
                await request.dispose()

            browser = await playwright.chromium.launch()
            try:
                url = f"{base_url}/listings"
                viewport = {"width": 1440, "height": 900}
                for _ in range(WARMUP_REQUESTS):
                    page = await browser.new_page(viewport=viewport)
                    try:
                        await _measure_navigation(page, url)
                    finally:
                        await page.close()

                # Кожна сторінка має власний ізольований контекст і холодний кеш.
                pages = [
                    await browser.new_page(viewport=viewport)
                    for _ in range(CONCURRENT_USERS)
                ]
                results = await asyncio.gather(
                    *(_measure_navigation(page, url) for page in pages),
                    return_exceptions=True,
                )
                failures = [
                    result for result in results if isinstance(result, BaseException)
                ]
                durations = [result for result in results if isinstance(result, float)]
                # Collect diagnostics after every navigation has finished.
                phases = await asyncio.gather(
                    *(page.evaluate(CATALOG_PHASES_SCRIPT) for page in pages)
                )
                for phase in ("before_api", "api_request", "after_api"):
                    samples = [sample[phase] for sample in phases if sample]
                    if samples:
                        print(
                            f"[PERF-001] {phase} p95={_p95(samples):.2f} ms "
                            f"(n={len(samples)}/{CONCURRENT_USERS})"
                        )
                assert (
                    not failures
                ), f"{len(failures)}/{CONCURRENT_USERS} failed: {failures[0]}"
                assert len(durations) == CONCURRENT_USERS
                return durations
            finally:
                await browser.close()

    durations = asyncio.run(run())
    p95 = _p95(durations)
    print(
        f"[PERF-001] p95={p95:.2f} ms, "
        f"successful navigations={len(durations)}/{CONCURRENT_USERS}"
    )
    assert p95 <= 300, f"PERF-001: browser p95 {p95:.2f} ms > 300 ms"
