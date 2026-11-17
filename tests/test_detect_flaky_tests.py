from pathlib import Path

from scripts.detect_flaky_tests import (
    RunResult,
    build_markdown,
    inconsistent_tests,
    outcome_matrix,
    parse_junit_report,
)


def _write_junit(path: Path, outcome: str) -> None:
    child = {
        "passed": "",
        "failed": '<failure message="boom" />',
        "error": '<error message="broken" />',
        "skipped": '<skipped message="later" />',
    }[outcome]
    path.write_text(
        '<testsuite tests="1"><testcase classname="tests.test_demo" name="test_x">'
        f"{child}</testcase></testsuite>",
        encoding="utf-8",
    )


def test_parse_junit_report_recognizes_each_outcome(tmp_path: Path) -> None:
    """[TP-057] Розпізнає всі підтримувані результати з JUnit XML."""
    for outcome in ("passed", "failed", "error", "skipped"):
        report = tmp_path / f"{outcome}.xml"
        _write_junit(report, outcome)
        assert parse_junit_report(report) == {"tests.test_demo::test_x": outcome}


def test_inconsistent_tests_includes_missing_and_changed_outcomes(
    tmp_path: Path,
) -> None:
    """[TP-057] Виявляє зміну результату й тест, відсутній у повторі."""
    first = RunResult(
        1, 0, {"a::test": "passed", "b::test": "passed"}, tmp_path / "1.xml"
    )
    second = RunResult(2, 1, {"a::test": "failed"}, tmp_path / "2.xml")

    matrix = outcome_matrix([first, second])

    assert matrix == {
        "a::test": ["passed", "failed"],
        "b::test": ["passed", "not-run"],
    }
    assert inconsistent_tests(matrix) == matrix


def test_markdown_reports_flaky_and_stable_failures(tmp_path: Path) -> None:
    """[TP-057] Розділяє нестабільні та стабільно зламані тести у звіті."""
    results = [
        RunResult(
            1,
            1,
            {"flaky::test[param|value]": "passed", "broken::test": "failed"},
            tmp_path / "run-01.xml",
        ),
        RunResult(
            2,
            1,
            {"flaky::test[param|value]": "failed", "broken::test": "failed"},
            tmp_path / "run-02.xml",
        ),
    ]

    markdown, count = build_markdown(results, ["pytest", "-q"], "abc123")

    assert count == 1
    assert "`flaky::test[param\\|value]`" in markdown
    assert "`broken::test`" in markdown
    assert "`abc123`" in markdown
