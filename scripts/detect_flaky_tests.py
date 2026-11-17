"""Run the same pytest suite repeatedly and report inconsistent outcomes.

Lab 10 bonus: the script keeps every JUnit report, compares each test across
runs and writes a Markdown summary suitable for a GitHub Actions artifact.
"""

from __future__ import annotations

import argparse
import os
import subprocess
import sys
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from xml.etree import ElementTree


@dataclass(frozen=True)
class RunResult:
    """One pytest run and its per-test outcomes."""

    number: int
    exit_code: int
    outcomes: dict[str, str]
    report: Path


def parse_junit_report(path: Path) -> dict[str, str]:
    """Return stable pytest node-like names mapped to JUnit outcomes."""
    outcomes: dict[str, str] = {}
    root = ElementTree.parse(path).getroot()
    for case in root.iter("testcase"):
        class_name = case.get("classname", "").strip()
        test_name = case.get("name", "unknown").strip()
        node_id = f"{class_name}::{test_name}" if class_name else test_name
        if case.find("failure") is not None:
            outcome = "failed"
        elif case.find("error") is not None:
            outcome = "error"
        elif case.find("skipped") is not None:
            outcome = "skipped"
        else:
            outcome = "passed"
        outcomes[node_id] = outcome
    return outcomes


def outcome_matrix(results: list[RunResult]) -> dict[str, list[str]]:
    """Align all observed tests; absent tests are explicit `not-run` values."""
    tests = sorted({test for result in results for test in result.outcomes})
    return {
        test: [result.outcomes.get(test, "not-run") for result in results]
        for test in tests
    }


def inconsistent_tests(matrix: dict[str, list[str]]) -> dict[str, list[str]]:
    """Select tests whose outcome differs between repeated runs."""
    return {test: states for test, states in matrix.items() if len(set(states)) > 1}


def _markdown_code(value: str) -> str:
    """Escape a test identifier so it cannot break a Markdown table."""
    return f"`{value.replace('|', r'\|')}`"


def _markdown_table(matrix: dict[str, list[str]], runs: int) -> list[str]:
    headers = ["Тест", *(f"Запуск {number}" for number in range(1, runs + 1))]
    separator = ["---", *("---:" for _ in range(runs))]
    lines = [f"| {' | '.join(headers)} |", f"| {' | '.join(separator)} |"]
    for test, states in matrix.items():
        lines.append(f"| {_markdown_code(test)} | {' | '.join(states)} |")
    return lines


def build_markdown(
    results: list[RunResult], command: list[str], commit_sha: str
) -> tuple[str, int]:
    """Build the human-readable report and return its flaky-test count."""
    matrix = outcome_matrix(results)
    flaky = inconsistent_tests(matrix)
    consistently_bad = {
        test: states
        for test, states in matrix.items()
        if len(set(states)) == 1 and states[0] in {"failed", "error", "not-run"}
    }
    generated_at = datetime.now(UTC).isoformat(timespec="seconds")
    lines = [
        "# Пошук нестабільних тестів — Lab 10, бонус",
        "",
        f"- **Час формування (UTC):** {generated_at}",
        f"- **Коміт:** `{commit_sha}`",
        f"- **Кількість повторів:** {len(results)}",
        f"- **Команда:** `{' '.join(command)}`",
        "",
        "## Результати запусків",
        "",
        "| Запуск | Exit code | JUnit-звіт |",
        "|---:|---:|---|",
    ]
    lines.extend(
        f"| {result.number} | {result.exit_code} | `{result.report.name}` |"
        for result in results
    )
    lines.extend(["", "## Нестабільні тести", ""])
    if flaky:
        lines.extend(_markdown_table(flaky, len(results)))
    else:
        lines.append(
            "**Не знайдено:** результат кожного зібраного тесту був однаковим "
            "у всіх повторах."
        )
    lines.extend(["", "## Стабільні помилки або неповні запуски", ""])
    if consistently_bad:
        lines.extend(_markdown_table(consistently_bad, len(results)))
    else:
        lines.append("Стабільних помилок і неповних запусків не знайдено.")
    lines.extend(
        [
            "",
            "> Тест вважається нестабільним лише тоді, коли його стан "
            "(`passed`, `failed`, `error`, `skipped` або `not-run`) відрізняється "
            "між повторами на тому самому коміті.",
            "",
        ]
    )
    return "\n".join(lines), len(flaky)


def run_repeated_suite(
    runs: int, results_dir: Path, pytest_args: list[str]
) -> list[RunResult]:
    """Execute pytest sequentially, preserving all reports even after failures."""
    results_dir.mkdir(parents=True, exist_ok=True)
    results: list[RunResult] = []
    for number in range(1, runs + 1):
        report = results_dir / f"run-{number:02d}.xml"
        command = [
            sys.executable,
            "-m",
            "pytest",
            *pytest_args,
            f"--junitxml={report}",
        ]
        print(f"[run {number}/{runs}] {' '.join(command)}", flush=True)
        completed = subprocess.run(command, check=False)
        if report.exists():
            outcomes = parse_junit_report(report)
        else:
            outcomes = {}
        results.append(
            RunResult(
                number=number,
                exit_code=completed.returncode,
                outcomes=outcomes,
                report=report,
            )
        )
    return results


def _commit_sha() -> str:
    github_sha = os.environ.get("GITHUB_SHA")
    if github_sha:
        return github_sha
    completed = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        check=False,
        capture_output=True,
        text=True,
    )
    return completed.stdout.strip() or "unknown"


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Run pytest repeatedly and report tests with changing outcomes."
    )
    parser.add_argument("--runs", type=int, default=5)
    parser.add_argument("--results-dir", type=Path, default=Path("flaky-test-results"))
    parser.add_argument(
        "pytest_args",
        nargs=argparse.REMAINDER,
        help="Arguments after `--` are forwarded to pytest.",
    )
    args = parser.parse_args()
    if args.runs < 5:
        parser.error("Lab 10 requires at least five runs")
    pytest_args = args.pytest_args
    if pytest_args[:1] == ["--"]:
        pytest_args = pytest_args[1:]
    if not pytest_args:
        pytest_args = ["-q"]

    results = run_repeated_suite(args.runs, args.results_dir, pytest_args)
    command = [
        "python",
        "scripts/detect_flaky_tests.py",
        "--runs",
        str(args.runs),
        "--",
        *pytest_args,
    ]
    report, flaky_count = build_markdown(results, command, _commit_sha())
    report_path = args.results_dir / "report.md"
    report_path.write_text(report, encoding="utf-8")
    print(report)
    print(f"Report: {report_path}")

    has_failed_run = any(result.exit_code != 0 for result in results)
    return 1 if flaky_count or has_failed_run else 0


if __name__ == "__main__":
    raise SystemExit(main())
