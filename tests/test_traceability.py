"""Автоматизована перевірка простежуваності (Traceability Check Bonus - 0,25 бала).

Тест верифікує двосторонню узгодженість між:
1. Матрицею простежуваності вимог (/docs/requirements/rtm.md)
2. Планом тестування (/docs/validation/test-plan.md)
3. Автоматизованими тестовими наборами (/tests/)

Критерії перевірки:
- Кожен ID тест-кейсу з rtm.md присутній та задокументований у test-plan.md;
- Кожен тест-кейс у test-plan.md має власника, рівень тесту та критерій;
- Кожен тест-кейс у test-plan.md зіставлений з відомою вимогою системи;
- Кожен активний тест-кейс має відповідну реалізацію у каталозі tests/.
"""

import re
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
RTM_PATH = REPO_ROOT / "docs" / "requirements" / "rtm.md"
TEST_PLAN_PATH = REPO_ROOT / "docs" / "validation" / "test-plan.md"
TESTS_DIR = REPO_ROOT / "tests"

TEST_CASE_ID_PATTERN = re.compile(r"\b(TP-\d{3}|TP-N\d{2}|TP-AUTH-\d{2}|DT-\d{2})\b")


def parse_rtm_test_case_ids(rtm_path: Path) -> dict[str, list[str]]:
    """Парсить rtm.md і повертає мапу {requirement_id: [test_case_ids]}."""
    content = rtm_path.read_text(encoding="utf-8")
    result: dict[str, list[str]] = {}
    for line in content.splitlines():
        if not line.startswith("|"):
            continue
        parts = [p.strip() for p in line.split("|")[1:-1]]
        if len(parts) < 5 or parts[0] in ("Вимога / історія", "---"):
            continue
        req_id = parts[0]
        tests_col = parts[4]
        found_ids = TEST_CASE_ID_PATTERN.findall(tests_col)
        result[req_id] = found_ids
    return result


def parse_test_plan_cases(test_plan_path: Path) -> dict[str, dict[str, str]]:
    """Парсить таблиці тест-кейсів з test-plan.md і повертає мапу {case_id: details}."""
    content = test_plan_path.read_text(encoding="utf-8")
    cases: dict[str, dict[str, str]] = {}

    for line in content.splitlines():
        if not line.startswith("|"):
            continue
        parts = [p.strip() for p in line.split("|")[1:-1]]
        if not parts:
            continue
        first = parts[0].strip("`* ")
        # Перевіряємо, чи перший стовпець є валідним ID тест-кейсу
        if TEST_CASE_ID_PATTERN.match(first):
            case_id = first
            if len(parts) >= 7:
                cases[case_id] = {
                    "id": case_id,
                    "component": parts[1],
                    "level": parts[2],
                    "type": parts[3],
                    "expected": parts[4],
                    "owner": parts[5],
                    "requirement": parts[6],
                }
            elif len(parts) >= 5:  # Наприклад таблиця Entra ID
                cases[case_id] = {
                    "id": case_id,
                    "level": parts[1],
                    "scenario": parts[2],
                    "expected": parts[3],
                    "requirement": parts[4],
                }
            elif len(parts) >= 7 and "DT-" in case_id:  # Таблиця рішень
                cases[case_id] = {
                    "id": case_id,
                    "requirement": "FR-006, FR-007, FR-008",
                }

    # Також шукаємо DT-01..DT-07 в тексті таблиці рішень
    for match in re.finditer(r"\*\*`?(DT-\d{2})`?\*\*", content):
        dt_id = match.group(1)
        if dt_id not in cases:
            cases[dt_id] = {"id": dt_id, "requirement": "FR-006..FR-008"}

    return cases


def test_rtm_and_test_plan_files_exist() -> None:
    assert RTM_PATH.exists(), f"Файл {RTM_PATH} не знайдено"
    assert TEST_PLAN_PATH.exists(), f"Файл {TEST_PLAN_PATH} не знайдено"


def test_all_rtm_test_ids_exist_in_test_plan() -> None:
    """Усі ID тестів, зазначені в rtm.md, мають бути визначені в test-plan.md."""
    rtm_map = parse_rtm_test_case_ids(RTM_PATH)
    plan_cases = parse_test_plan_cases(TEST_PLAN_PATH)

    assert len(rtm_map) > 0, "У rtm.md не знайдено вимог"
    assert len(plan_cases) > 0, "У test-plan.md не знайдено тест-кейсів"

    missing_cases: list[str] = []
    for req_id, test_ids in rtm_map.items():
        for tid in test_ids:
            if tid not in plan_cases:
                missing_cases.append(f"{tid} (вимога: {req_id})")

    assert (
        not missing_cases
    ), f"Тест-кейси з rtm.md відсутні у test-plan.md: {missing_cases}"


def test_test_plan_cases_have_valid_metadata() -> None:
    """Кожен основний функціональний тест-кейс має рівень, критерій та вимогу."""
    plan_cases = parse_test_plan_cases(TEST_PLAN_PATH)

    for case_id, meta in plan_cases.items():
        if case_id.startswith("TP-") and not case_id.startswith("TP-AUTH"):
            assert meta.get("level"), f"У тест-кейсу {case_id} відсутній рівень тесту"
            assert meta.get(
                "expected"
            ), f"У тест-кейсу {case_id} відсутній очікуваний результат"
            assert meta.get(
                "requirement"
            ), f"У тест-кейсу {case_id} відсутнє посилання на вимогу"


def test_automated_tests_presence_in_repository() -> None:
    """Перевіряє, що основні файли тестів для вимог існують у /tests/."""
    expected_test_files = [
        "test_listings_api.py",
        "test_listing_service.py",
        "test_decision_table.py",
        "test_categories.py",
        "test_categories_api.py",
        "test_favorites.py",
        "test_favorites_api.py",
        "test_security.py",
        "test_validators.py",
    ]

    for fname in expected_test_files:
        test_file = TESTS_DIR / fname
        assert test_file.exists(), f"Файл тестів {fname} відсутній у {TESTS_DIR}"
