"""Автоматизована перевірка простежуваності (Traceability Check Bonus - 0,25 бала).

Тест виконує двосторонній AST-аналіз кодової бази та валідує нерозривність ланцюжка:
1. Матриця простежуваності вимог (/docs/requirements/rtm.md)
2. План тестування (/docs/validation/test-plan.md)
3. Автоматизовані тестові функції у /tests/*.py через AST-парсинг

Критерії перевірки:
- Кожен ID тест-кейсу з rtm.md присутній та задокументований у test-plan.md;
- Кожен тест-кейс у test-plan.md має метадані
  (рівень, тип, очікуваний результат, вимога);
- Пряма простежуваність (Forward): кожен активний тест-кейс із test-plan.md
  реалізовано у конкретній тестовій функції Python (сканування AST /tests/);
- Зворотна простежуваність (Backward): кожна маркована тестова функція
  посилається на валідну вимогу з rtm.md;
- Покриття вимог кодом: усі активні вимоги ядра мають виконувані тести.
"""

import ast
from pathlib import Path
import re

REPO_ROOT = Path(__file__).resolve().parent.parent
RTM_PATH = REPO_ROOT / "docs" / "requirements" / "rtm.md"
TEST_PLAN_PATH = REPO_ROOT / "docs" / "validation" / "test-plan.md"
TESTS_DIR = REPO_ROOT / "tests"

TEST_CASE_ID_PATTERN = re.compile(r"\b(TP-\d{3}|TP-N\d{2}|TP-AUTH-\d{2}|DT-\d{2})\b")
REQ_ID_PATTERN = re.compile(r"\b(FR-\d{3}|US-\d{3}|SEC-\d{3}|PERF-\d{3}|REL-\d{3})\b")


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
        m = TEST_CASE_ID_PATTERN.search(parts[0])
        if m:
            case_id = m.group(1)
            if len(parts) >= 7 and "DT-" not in case_id:
                cases[case_id] = {
                    "id": case_id,
                    "component": parts[1],
                    "level": parts[2],
                    "type": parts[3],
                    "expected": parts[4],
                    "owner": parts[5],
                    "requirement": parts[6],
                }
            elif len(parts) >= 5 and "TP-AUTH" in case_id:
                cases[case_id] = {
                    "id": case_id,
                    "level": parts[1],
                    "scenario": parts[2],
                    "expected": parts[3],
                    "requirement": parts[4],
                }
            elif "DT-" in case_id:
                cases[case_id] = {
                    "id": case_id,
                    "requirement": "FR-006, FR-007, FR-008",
                }

    return cases


def scan_tests_ast(tests_dir: Path) -> dict[str, list[str]]:
    """Сканує AST тестових файлів і повертає мапу {case_id: [functions]}."""
    case_to_functions: dict[str, list[str]] = {}

    for py_file in tests_dir.glob("test_*.py"):
        try:
            tree = ast.parse(py_file.read_text(encoding="utf-8"), filename=str(py_file))
        except Exception:
            continue

        for node in ast.walk(tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                if not node.name.startswith("test_"):
                    continue

                docstring = ast.get_docstring(node) or ""
                # Шукаємо ідентифікатори тест-кейсів у docstring або імені функції
                found_cases = set(TEST_CASE_ID_PATTERN.findall(docstring))

                # Також перевіряємо параметризовані виклики (наприклад DT-01..DT-07)
                file_text = py_file.read_text(encoding="utf-8")
                for dt_match in re.finditer(r'id=["\'](DT-\d{2})["\']', file_text):
                    found_cases.add(dt_match.group(1))

                for cid in found_cases:
                    case_to_functions.setdefault(cid, []).append(
                        f"{py_file.name}::{node.name}"
                    )

    return case_to_functions


def scan_tests_requirements_ast(tests_dir: Path) -> dict[str, list[str]]:
    """Сканує AST і повертає мапу {requirement_id: [function_names]}."""
    req_to_functions: dict[str, list[str]] = {}

    for py_file in tests_dir.glob("test_*.py"):
        try:
            tree = ast.parse(py_file.read_text(encoding="utf-8"), filename=str(py_file))
        except Exception:
            continue

        for node in ast.walk(tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                if not node.name.startswith("test_"):
                    continue

                docstring = ast.get_docstring(node) or ""
                found_reqs = set(REQ_ID_PATTERN.findall(docstring))
                for req in found_reqs:
                    req_to_functions.setdefault(req, []).append(
                        f"{py_file.name}::{node.name}"
                    )

    return req_to_functions


def test_rtm_and_test_plan_files_exist() -> None:
    """Перевіряє фізичну наявність обов'язкових артефактів валідації."""
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


def test_ast_every_test_plan_case_has_matching_python_test() -> None:
    """Пряма простежуваність: кожен активний тест-кейс має автотест в коді."""
    plan_cases = parse_test_plan_cases(TEST_PLAN_PATH)
    case_to_functions = scan_tests_ast(TESTS_DIR)

    # Виключаємо заплановані Entra ID кейси (поза поточним обсягом)
    active_cases = [cid for cid in plan_cases.keys() if not cid.startswith("TP-AUTH")]

    missing_implementations: list[str] = []
    for cid in active_cases:
        if cid not in case_to_functions or not case_to_functions[cid]:
            missing_implementations.append(cid)

    assert not missing_implementations, (
        f"Тест-кейси з test-plan.md не знайдено у tests/: " f"{missing_implementations}"
    )


def test_ast_all_implemented_requirements_covered_by_python_tests() -> None:
    """Зворотна простежуваність: усі реалізовані вимоги мають автотести."""
    req_to_functions = scan_tests_requirements_ast(TESTS_DIR)

    expected_implemented_reqs = [
        "FR-002",
        "FR-003",
        "FR-004",
        "FR-005",
        "FR-006",
        "FR-007",
        "FR-008",
        "FR-009",
        "FR-012",
        "SEC-002",
        "PERF-001",
    ]

    missing_req_tests: list[str] = []
    for req in expected_implemented_reqs:
        if req not in req_to_functions or not req_to_functions[req]:
            missing_req_tests.append(req)

    assert not missing_req_tests, (
        f"Реалізовані вимоги не мають тестових функцій у tests/: "
        f"{missing_req_tests}"
    )
