"""Автоматичний підрахунок 4 метрик DORA із GitHub Actions API (Лаб 10, Бонус 1).

Скрипт читає історію запусків гілки `main` із збереженого експорту
`docs/ci-cd/evidence/main-runs-2026-10-30-to-2026-11-13.json` або напряму з
GitHub Actions REST API (`--fetch-github`), відокремлює очікування в черзі від
самого виконання конвеєра, обчислює 4 метрики DORA за строгими правилами Лаб 10
і формує звіт `docs/ci-cd/dora-metrics-auto.md` з поясненням розбіжностей
щодо ручного підрахунку Етапу 2.
"""

from __future__ import annotations

import argparse
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
import json
import os
from pathlib import Path
import re
import statistics
from typing import Any

import requests

REPO_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_REPO = "ukma-fin-ssdm-2026/Next-Gen"
DEFAULT_SINCE = "2026-10-30"
DEFAULT_UNTIL = "2026-11-13"
DEFAULT_EVIDENCE = (
    REPO_ROOT
    / "docs"
    / "ci-cd"
    / "evidence"
    / "main-runs-2026-10-30-to-2026-11-13.json"
)
DEFAULT_OUTPUT = REPO_ROOT / "docs" / "ci-cd" / "dora-metrics-auto.md"
TRACKED_WORKFLOWS = ("CI", "Deploy API docs")
GITHUB_API_TIMEOUT_SECONDS = 20

# Незалежний базовий рівень ручного аналізу з docs/ci-cd/dora-summary.md (Етап 2)
MANUAL_BASELINE: dict[str, Any] = {
    "period_days": 15,
    "total_units": 60,
    "success_deployments": 48,
    "failure_units": 8,
    "cancelled_units": 4,
    "deployment_freq_per_day": 3.2,
    "deployment_freq_per_week": 22.4,
    "lead_time_median_s": 1463,  # 24 хв 23 с
    "lead_time_mean_s": 8727,  # 2 год 25 хв 27 с
    "lead_time_p75_s": 3993,  # 1 год 6 хв 33 с
    "cfr_no_cancelled_pct": 14.3,
    "cfr_with_cancelled_pct": 20.0,
    "per_failure_median_s": 21767,  # 6 год 2 хв 47 с
    "per_failure_mean_s": 23038,  # 6 год 23 хв 58 с
    "incident_episode_s": 56313,  # 15 год 38 хв 33 с
}


@dataclass(frozen=True)
class DeliveryUnit:
    """Одна злита зміна на `main` із пов'язаними запусками CI та Deploy API docs."""

    unit_number: int
    commit_sha: str
    full_sha: str
    pr_number: int | None
    pr_url: str | None
    first_commit_at: datetime
    completed_at: datetime
    queue_seconds: int
    execution_seconds: int
    status: str  # "success", "failure", "cancelled"
    note: str = ""
    workflow_runs: tuple[dict[str, Any], ...] = ()

    @property
    def lead_time_seconds(self) -> int:
        return max(0, int((self.completed_at - self.first_commit_at).total_seconds()))

    @property
    def pre_ci_seconds(self) -> int:
        return max(
            0, self.lead_time_seconds - self.queue_seconds - self.execution_seconds
        )


def _parse_iso(ts: str) -> datetime:
    return datetime.fromisoformat(ts.replace("Z", "+00:00")).astimezone(timezone.utc)


def _format_iso(dt: datetime) -> str:
    return dt.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _format_duration(seconds: float) -> str:
    total = int(round(seconds))
    days, rem = divmod(total, 86400)
    hours, rem = divmod(rem, 3600)
    minutes, secs = divmod(rem, 60)
    parts: list[str] = []
    if days:
        day_word = "день" if days == 1 else "дні" if 2 <= days % 10 <= 4 else "днів"
        parts.append(f"{days} {day_word}")
    if hours:
        parts.append(f"{hours} год")
    if minutes:
        parts.append(f"{minutes} хв")
    if secs or not parts:
        parts.append(f"{secs} с")
    return " ".join(parts)


def _percentile(values: list[int], q: float) -> float:
    """Лінійна інтерполяція q-го квантиля (узгоджено з numpy/pandas)."""
    if not values:
        return 0.0
    ordered = sorted(values)
    idx = q * (len(ordered) - 1)
    lo = int(idx)
    hi = min(lo + 1, len(ordered) - 1)
    return ordered[lo] + (idx - lo) * (ordered[hi] - ordered[lo])


def _github_headers() -> dict[str, str]:
    headers = {
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
    }
    token = os.getenv("GITHUB_TOKEN") or os.getenv("GH_TOKEN")
    if token:
        headers["Authorization"] = f"Bearer {token.strip()}"
    return headers


def _run_id(run: dict[str, Any]) -> int:
    return int(run.get("id") or run.get("databaseId") or 0)


def _run_created_at(run: dict[str, Any]) -> datetime:
    return _parse_iso(str(run.get("created_at") or run.get("createdAt") or ""))


def _run_started_at(run: dict[str, Any]) -> datetime:
    ts = (
        run.get("run_started_at")
        or run.get("runStartedAt")
        or run.get("created_at")
        or run.get("createdAt")
        or ""
    )
    return _parse_iso(str(ts))


def _run_updated_at(run: dict[str, Any]) -> datetime:
    return _parse_iso(str(run.get("updated_at") or run.get("updatedAt") or ""))


def _saved_run_fp(run: dict[str, Any]) -> tuple[Any, ...]:
    return (
        _run_id(run),
        int(run.get("attempt") or run.get("run_attempt") or 1),
        str(run.get("conclusion")),
        _run_created_at(run),
        _run_started_at(run),
        _run_updated_at(run),
    )


def _normalize_unit_workflow_run(
    run: dict[str, Any],
    cached_runs_by_id: dict[int, dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """Нормалізує об'єкт workflow-запуску до схеми `delivery_units.workflow_runs`."""
    run_id = _run_id(run)
    cached_run = cached_runs_by_id.get(run_id) if cached_runs_by_id else None
    workflow_id = run.get("workflow_id")
    if workflow_id is None and cached_run is not None:
        workflow_id = cached_run.get("workflow_id")
    html_url = (
        run.get("html_url")
        or run.get("url")
        or (cached_run.get("html_url") if cached_run else "")
        or ""
    )
    return {
        "id": run_id,
        "name": str(run.get("name") or run.get("workflowName") or ""),
        "workflow_id": int(workflow_id) if workflow_id is not None else None,
        "status": str(run.get("status") or "completed"),
        "conclusion": run.get("conclusion"),
        "run_attempt": int(run.get("run_attempt") or run.get("attempt") or 1),
        "created_at": _format_iso(_run_created_at(run)),
        "run_started_at": _format_iso(_run_started_at(run)),
        "updated_at": _format_iso(_run_updated_at(run)),
        "html_url": str(html_url),
    }


def _normalize_raw_run(run: dict[str, Any]) -> dict[str, Any]:
    """Нормалізує сирий запис запуску GitHub Actions до схеми `github_runs_raw`."""
    return {
        "databaseId": _run_id(run),
        "workflowName": str(run.get("workflowName") or run.get("name") or ""),
        "headSha": str(run.get("headSha") or run.get("head_sha") or ""),
        "status": str(run.get("status") or "completed"),
        "conclusion": run.get("conclusion"),
        "attempt": int(run.get("attempt") or run.get("run_attempt") or 1),
        "event": str(run.get("event") or "push"),
        "createdAt": _format_iso(_run_created_at(run)),
        "runStartedAt": _format_iso(_run_started_at(run)),
        "updatedAt": _format_iso(_run_updated_at(run)),
        "displayTitle": str(run.get("displayTitle") or run.get("display_title") or ""),
        "url": str(run.get("url") or run.get("html_url") or ""),
    }


def _fetch_unit_job_timings(
    base_url: str,
    headers: dict[str, str],
    group: list[dict[str, Any]],
) -> tuple[datetime, datetime]:
    """Отримує мінімальний старт і максимальне завершення завдань одиниці."""
    started_times: list[datetime] = []
    completed_times: list[datetime] = []
    for run in group:
        if isinstance(run.get("jobs"), list):
            jobs = run["jobs"]
        else:
            run_id = run.get("id") or run.get("databaseId")
            j_resp = requests.get(
                f"{base_url}/actions/runs/{run_id}/jobs",
                headers=headers,
                params={"per_page": 100},
                timeout=GITHUB_API_TIMEOUT_SECONDS,
            )
            if not j_resp.ok:
                raise RuntimeError(
                    f"Не вдалося отримати завдання для запуску GitHub Actions {run_id}"
                )
            jobs = j_resp.json().get("jobs", [])
        for job in jobs:
            if job.get("started_at"):
                started_times.append(_parse_iso(job["started_at"]))
            if job.get("completed_at"):
                completed_times.append(_parse_iso(job["completed_at"]))
    if not started_times or not completed_times:
        raise RuntimeError(
            "Не вдалося отримати часові мітки завдань для одиниці постачання"
        )
    return min(started_times), max(completed_times)


def fetch_units_from_github() -> tuple[list[DeliveryUnit], list[dict[str, Any]]]:
    """Отримує запуски CI/CD на `main` через GitHub Actions REST API."""
    headers = _github_headers()
    base_url = f"https://api.github.com/repos/{DEFAULT_REPO}"
    start_dt = _parse_iso(f"{DEFAULT_SINCE}T00:00:00Z")
    end_dt = _parse_iso(f"{DEFAULT_UNTIL}T23:59:59Z")

    fallback_by_sha: dict[str, dict[str, Any]] = {}
    saved_runs_by_sha: dict[str, list[tuple[Any, ...]]] = {}
    if DEFAULT_EVIDENCE.exists():
        saved = json.loads(DEFAULT_EVIDENCE.read_text(encoding="utf-8"))
        for item in saved.get("delivery_units", []):
            fallback_by_sha[item["full_sha"]] = item
            fallback_by_sha[item["commit_sha"]] = item
        for raw_run in saved.get("github_runs_raw", []):
            raw_sha = raw_run.get("headSha") or raw_run.get("head_sha")
            if raw_sha:
                saved_runs_by_sha.setdefault(raw_sha, []).append(_saved_run_fp(raw_run))

    raw_runs: list[dict[str, Any]] = []
    for page in range(1, 101):
        resp = requests.get(
            f"{base_url}/actions/runs",
            headers=headers,
            params={"branch": "main", "per_page": 100, "page": page},
            timeout=GITHUB_API_TIMEOUT_SECONDS,
        )
        resp.raise_for_status()
        batch = resp.json().get("workflow_runs", [])
        if not batch:
            break
        raw_runs.extend(batch)
        oldest = min(_run_created_at(run) for run in batch)
        if oldest < start_dt - timedelta(days=1) or len(batch) < 100:
            break
    else:
        raise RuntimeError(
            "Історія запусків GitHub Actions не досягла початку періоду спостереження"
        )

    by_sha: dict[str, list[dict[str, Any]]] = {}
    for run in raw_runs:
        run_name = run.get("name") or run.get("workflowName")
        if run_name not in TRACKED_WORKFLOWS:
            continue
        if run.get("event") in {"workflow_dispatch", "schedule"}:
            continue
        sha = str(run.get("head_sha") or run.get("headSha") or "")
        if not sha:
            continue
        # Виключаємо незалежні коміти Dependabot або не-merge запуски поза вибіркою.
        title = str(run.get("display_title") or run.get("displayTitle") or "")
        if "dependabot" in title.lower() and sha not in fallback_by_sha:
            continue
        by_sha.setdefault(sha, []).append(run)

    units: list[DeliveryUnit] = []
    filtered_raw: list[dict[str, Any]] = []
    ordered_groups = sorted(
        by_sha.items(),
        key=lambda item: (
            min(_run_created_at(r) for r in item[1]),
            max(_run_updated_at(r) for r in item[1]),
        ),
    )

    pr_first_commit_cache: dict[int, datetime] = {}

    for sha, group in ordered_groups:
        created_min = min(_run_created_at(r) for r in group)
        group_max_updated = max(_run_updated_at(r) for r in group)

        conclusions = {r.get("conclusion") for r in group}
        if "failure" in conclusions or "timed_out" in conclusions:
            unit_status = "failure"
        elif "cancelled" in conclusions:
            unit_status = "cancelled"
        elif conclusions == {"success"}:
            unit_status = "success"
        else:
            unit_status = "failure"

        cached = fallback_by_sha.get(sha) or fallback_by_sha.get(sha[:7])
        cached_wf_runs = cached.get("workflow_runs", []) if cached else []
        cached_runs_by_id = {
            int(item["id"]): item for item in cached_wf_runs if item.get("id")
        }
        cached_order = {
            int(item["id"]): idx
            for idx, item in enumerate(cached_wf_runs)
            if item.get("id")
        }
        ordered_group = sorted(
            group,
            key=lambda r: (
                cached_order.get(_run_id(r), len(cached_order)),
                _format_iso(_run_created_at(r)),
                _run_id(r),
            ),
        )

        title = str(
            ordered_group[0].get("display_title")
            or ordered_group[0].get("displayTitle")
            or ""
        )
        pr_match = re.search(r"#(\d+)", title)
        cached_pr = cached.get("pr_number") if cached else None
        pr_number: int | None = (
            int(pr_match.group(1))
            if pr_match
            else (int(cached_pr) if cached_pr is not None else None)
        )
        pr_url = (
            cached.get("pr_url")
            if cached and cached.get("pr_url")
            else (
                f"https://github.com/{DEFAULT_REPO}/pull/{pr_number}"
                if pr_number is not None
                else None
            )
        )
        note = (
            str(cached.get("note", ""))
            if cached and unit_status == cached.get("status")
            else ""
        )

        live_fp = sorted(_saved_run_fp(r) for r in ordered_group)
        saved_fp = sorted(saved_runs_by_sha.get(sha, []))
        if cached and saved_fp and live_fp == saved_fp:
            completed_at = _parse_iso(cached["completed_at"])
            queue_seconds = int(cached["queue_seconds"])
            execution_seconds = int(cached["execution_seconds"])
        else:
            if created_min > end_dt or group_max_updated < start_dt:
                continue
            started_min, completed_at = _fetch_unit_job_timings(
                base_url, headers, ordered_group
            )
            queue_seconds = max(0, int((started_min - created_min).total_seconds()))
            execution_seconds = max(
                0, int((completed_at - started_min).total_seconds())
            )

        if not (start_dt <= completed_at <= end_dt):
            continue

        if cached and cached.get("first_commit_at"):
            first_commit_at = _parse_iso(cached["first_commit_at"])
        else:
            if pr_number is None:
                raise RuntimeError(
                    f"Не вдалося визначити час першого коміту для SHA {sha[:7]} "
                    f"(PR #{pr_number})"
                )
            if pr_number not in pr_first_commit_cache:
                c_resp = requests.get(
                    f"{base_url}/pulls/{pr_number}/commits",
                    headers=headers,
                    params={"per_page": 100},
                    timeout=GITHUB_API_TIMEOUT_SECONDS,
                )
                if not c_resp.ok:
                    raise RuntimeError(
                        f"Не вдалося визначити час першого коміту для SHA {sha[:7]} "
                        f"(PR #{pr_number})"
                    )
                commits_payload = c_resp.json()
                if not commits_payload:
                    raise RuntimeError(
                        f"Не вдалося визначити час першого коміту для SHA {sha[:7]} "
                        f"(PR #{pr_number})"
                    )
                dt = commits_payload[0]["commit"]["author"]["date"]
                pr_first_commit_cache[pr_number] = _parse_iso(dt)
            first_commit_at = pr_first_commit_cache[pr_number]

        unit_workflow_runs = tuple(
            _normalize_unit_workflow_run(r, cached_runs_by_id) for r in ordered_group
        )
        filtered_raw.extend(_normalize_raw_run(r) for r in ordered_group)
        units.append(
            DeliveryUnit(
                unit_number=len(units) + 1,
                commit_sha=sha[:7],
                full_sha=sha,
                pr_number=pr_number,
                pr_url=pr_url,
                first_commit_at=first_commit_at,
                completed_at=completed_at,
                queue_seconds=queue_seconds,
                execution_seconds=execution_seconds,
                status=unit_status,
                note=note,
                workflow_runs=unit_workflow_runs,
            )
        )
    return units, filtered_raw


def load_units_from_evidence() -> list[DeliveryUnit]:
    """Зчитує нормалізований JSON-експорт із `/docs/ci-cd/evidence/`."""
    payload = json.loads(DEFAULT_EVIDENCE.read_text(encoding="utf-8"))
    return [
        DeliveryUnit(
            unit_number=int(row["unit_number"]),
            commit_sha=str(row["commit_sha"]),
            full_sha=str(row["full_sha"]),
            pr_number=row.get("pr_number"),
            pr_url=row.get("pr_url"),
            first_commit_at=_parse_iso(row["first_commit_at"]),
            completed_at=_parse_iso(row["completed_at"]),
            queue_seconds=int(row["queue_seconds"]),
            execution_seconds=int(row["execution_seconds"]),
            status=str(row["status"]),
            note=str(row.get("note", "")),
            workflow_runs=tuple(row.get("workflow_runs", [])),
        )
        for row in payload["delivery_units"]
    ]


def save_evidence(
    units: list[DeliveryUnit],
    raw_runs: list[dict[str, Any]],
    period_days: int,
) -> None:
    """Зберігає нормалізовані одиниці постачання та сирі відповіді GitHub Actions."""
    normalized_raw = [_normalize_raw_run(r) for r in raw_runs]
    if not normalized_raw and units:
        for unit in units:
            for wf_run in unit.workflow_runs:
                enriched = {
                    **wf_run,
                    "headSha": (
                        wf_run.get("headSha") or wf_run.get("head_sha") or unit.full_sha
                    ),
                    "displayTitle": (
                        wf_run.get("displayTitle")
                        or wf_run.get("display_title")
                        or (f"PR #{unit.pr_number}" if unit.pr_number else "")
                    ),
                }
                normalized_raw.append(_normalize_raw_run(enriched))

    payload = {
        "metadata": {
            "repository": DEFAULT_REPO,
            "branch": "main",
            "period_start": DEFAULT_SINCE,
            "period_end": DEFAULT_UNTIL,
            "period_days": period_days,
            "workflows_tracked": list(TRACKED_WORKFLOWS),
            "delivery_units_count": len(units),
            "workflow_runs_count": len(normalized_raw),
            "source_api": (
                f"https://api.github.com/repos/{DEFAULT_REPO}/actions/runs?branch=main"
            ),
        },
        "delivery_units": [
            {
                "unit_number": unit.unit_number,
                "commit_sha": unit.commit_sha,
                "full_sha": unit.full_sha,
                "pr_number": unit.pr_number,
                "pr_url": unit.pr_url,
                "first_commit_at": _format_iso(unit.first_commit_at),
                "completed_at": _format_iso(unit.completed_at),
                "queue_seconds": unit.queue_seconds,
                "execution_seconds": unit.execution_seconds,
                "lead_time_seconds": unit.lead_time_seconds,
                "status": unit.status,
                "note": unit.note,
                "workflow_runs": list(unit.workflow_runs),
            }
            for unit in units
        ],
        "github_runs_raw": normalized_raw,
    }
    DEFAULT_EVIDENCE.parent.mkdir(parents=True, exist_ok=True)
    with open(DEFAULT_EVIDENCE, "w", encoding="utf-8") as ev_file:
        json.dump(payload, ev_file, ensure_ascii=False, indent=2)
        ev_file.write("\n")


def compute_metrics(units: list[DeliveryUnit], period_days: int) -> dict[str, Any]:
    """Обчислює 4 метрики DORA у двох розрізах та декомпозицію черги/виконання."""
    green = [u for u in units if u.status == "success"]
    failed = [u for u in units if u.status == "failure"]
    cancelled = [u for u in units if u.status == "cancelled"]
    weeks = period_days / 7.0

    # Час відновлення після невдалого розгортання:
    # Одиниці впорядковуємо за завершенням, щоб раніша зелена зміна не закрила збій.
    units_by_completion = sorted(units, key=lambda u: (u.completed_at, u.unit_number))

    # 1) Безперервні інциденти (від першого збою серії до першого наступного зеленого)
    incident_recoveries: list[int] = []
    incident_start: datetime | None = None
    for unit in units_by_completion:
        if unit.status == "failure" and incident_start is None:
            incident_start = unit.completed_at
        elif unit.status == "success" and incident_start is not None:
            incident_recoveries.append(
                int((unit.completed_at - incident_start).total_seconds())
            )
            incident_start = None

    # 2) Окремі червоні одиниці до найближчого наступного зеленого запуску
    per_failure_recoveries: list[int] = []
    unresolved_failures = 0
    for idx, unit in enumerate(units_by_completion):
        if unit.status != "failure":
            continue
        next_green = next(
            (u for u in units_by_completion[idx + 1 :] if u.status == "success"),
            None,
        )
        if next_green is not None:
            per_failure_recoveries.append(
                int((next_green.completed_at - unit.completed_at).total_seconds())
            )
        else:
            unresolved_failures += 1

    all_lt = [u.lead_time_seconds for u in units]
    green_lt = [u.lead_time_seconds for u in green]
    all_queue = [u.queue_seconds for u in units]
    all_exec = [u.execution_seconds for u in units]
    all_pre_ci = [u.pre_ci_seconds for u in units]
    green_queue = [u.queue_seconds for u in green]
    green_exec = [u.execution_seconds for u in green]
    green_pre_ci = [u.pre_ci_seconds for u in green]

    sum_lt = sum(all_lt) or 1
    sum_queue = sum(all_queue)
    sum_exec = sum(all_exec)
    sum_pre_ci = sum(all_pre_ci)
    sum_ci = (sum_queue + sum_exec) or 1

    sum_green_lt = sum(green_lt) or 1
    sum_green_queue = sum(green_queue)
    sum_green_exec = sum(green_exec)
    sum_green_pre_ci = sum(green_pre_ci)
    sum_green_ci = (sum_green_queue + sum_green_exec) or 1

    completed_non_cancelled = len(green) + len(failed)

    return {
        "period_days": period_days,
        "counts": {
            "total": len(units),
            "success": len(green),
            "failure": len(failed),
            "cancelled": len(cancelled),
        },
        "strict": {
            "deployment_freq_per_day": len(green) / period_days,
            "deployment_freq_per_week": len(green) / weeks,
            "lead_time_median_s": statistics.median(green_lt) if green_lt else 0,
            "lead_time_mean_s": statistics.mean(green_lt) if green_lt else 0,
            "lead_time_p75_s": _percentile(green_lt, 0.75),
            "cfr_no_cancelled_pct": (
                len(failed) / completed_non_cancelled * 100
                if completed_non_cancelled
                else 0.0
            ),
            "cfr_all_units_pct": len(failed) / len(units) * 100 if units else 0.0,
            "cfr_with_cancelled_pct": (
                (len(failed) + len(cancelled)) / len(units) * 100 if units else 0.0
            ),
            "incident_recoveries_s": incident_recoveries,
            "incident_recovery_median_s": (
                statistics.median(incident_recoveries) if incident_recoveries else 0
            ),
            "incident_recovery_mean_s": (
                statistics.mean(incident_recoveries) if incident_recoveries else 0
            ),
            "per_failure_median_s": (
                statistics.median(per_failure_recoveries)
                if per_failure_recoveries
                else 0
            ),
            "per_failure_mean_s": (
                statistics.mean(per_failure_recoveries) if per_failure_recoveries else 0
            ),
            "open_incident": incident_start is not None,
            "unresolved_failures": unresolved_failures,
        },
        "stage2_all_merges": {
            "deployment_freq_per_day": len(units) / period_days,
            "deployment_freq_per_week": len(units) / weeks,
            "lead_time_median_s": statistics.median(all_lt) if all_lt else 0,
            "lead_time_mean_s": statistics.mean(all_lt) if all_lt else 0,
            "lead_time_p75_s": _percentile(all_lt, 0.75),
            "lead_time_min_s": min(all_lt) if all_lt else 0,
            "lead_time_max_s": max(all_lt) if all_lt else 0,
        },
        "breakdown": {
            "queue_median_s": statistics.median(all_queue) if all_queue else 0,
            "queue_mean_s": statistics.mean(all_queue) if all_queue else 0,
            "queue_p75_s": _percentile(all_queue, 0.75),
            "queue_max_s": max(all_queue) if all_queue else 0,
            "exec_median_s": statistics.median(all_exec) if all_exec else 0,
            "exec_mean_s": statistics.mean(all_exec) if all_exec else 0,
            "exec_p75_s": _percentile(all_exec, 0.75),
            "exec_max_s": max(all_exec) if all_exec else 0,
            "green_queue_median_s": (
                statistics.median(green_queue) if green_queue else 0
            ),
            "green_queue_mean_s": statistics.mean(green_queue) if green_queue else 0,
            "green_queue_p75_s": _percentile(green_queue, 0.75),
            "green_exec_median_s": statistics.median(green_exec) if green_exec else 0,
            "green_exec_mean_s": statistics.mean(green_exec) if green_exec else 0,
            "green_exec_p75_s": _percentile(green_exec, 0.75),
            "green_pre_ci_share_lt_pct": sum_green_pre_ci / sum_green_lt * 100,
            "green_queue_share_lt_pct": sum_green_queue / sum_green_lt * 100,
            "green_exec_share_lt_pct": sum_green_exec / sum_green_lt * 100,
            "green_queue_share_ci_pct": sum_green_queue / sum_green_ci * 100,
            "green_exec_share_ci_pct": sum_green_exec / sum_green_ci * 100,
            "queue_share_lt_pct": sum_queue / sum_lt * 100,
            "exec_share_lt_pct": sum_exec / sum_lt * 100,
            "pre_ci_share_lt_pct": sum_pre_ci / sum_lt * 100,
            "queue_share_ci_pct": sum_queue / sum_ci * 100,
            "exec_share_ci_pct": sum_exec / sum_ci * 100,
            "ci_total_median_s": (
                statistics.median(
                    [u.queue_seconds + u.execution_seconds for u in units]
                )
                if units
                else 0
            ),
        },
    }


def _format_incident_recoveries(
    strict_metrics: dict[str, Any], failure_count: int = 0
) -> str:
    incidents = strict_metrics["incident_recoveries_s"]
    open_incident = bool(strict_metrics.get("open_incident"))
    unresolved_failures = int(strict_metrics.get("unresolved_failures", 0))
    if not incidents:
        if open_incident or failure_count > 0:
            return "не завершено (очікує успішного розгортання)"
        return "не спостерігалося"
    if len(incidents) == 1:
        base = _format_duration(incidents[0])
    else:
        per_incident = ", ".join(_format_duration(item) for item in incidents)
        med = _format_duration(strict_metrics["incident_recovery_median_s"])
        mean = _format_duration(strict_metrics["incident_recovery_mean_s"])
        base = f"медіана {med}, середнє {mean} (інциденти: {per_incident})"
    if open_incident:
        return (
            f"{base}; невідновлений інцидент "
            f"({unresolved_failures} ❌ очікує успішного розгортання)"
        )
    return base


def render_markdown(metrics: dict[str, Any]) -> str:
    """Генерує Markdown-звіт із результатами автоматичного підрахунку."""
    c = metrics["counts"]
    s = metrics["strict"]
    m2 = metrics["stage2_all_merges"]
    b = metrics["breakdown"]
    rec_episode = _format_incident_recoveries(s, failure_count=c["failure"])
    unresolved_failures = int(s.get("unresolved_failures", 0))
    has_open_or_failures = bool(s.get("open_incident")) or c["failure"] > 0
    unresolved_suffix = (
        f" ({unresolved_failures} ❌ не завершено)" if unresolved_failures else ""
    )
    per_fail_fallback = "не завершено" if has_open_or_failures else "не спостерігалося"
    rec_per_fail = (
        f"{_format_duration(s['per_failure_median_s'])}{unresolved_suffix}"
        if s["per_failure_median_s"]
        else per_fail_fallback
    )
    rec_per_fail_mean = (
        f"{_format_duration(s['per_failure_mean_s'])}{unresolved_suffix}"
        if s["per_failure_mean_s"]
        else per_fail_fallback
    )
    success_rate_cell = (
        f"**{c['success'] / c['total'] * 100:.1f}%** ({c['success']} із {c['total']})"
        if c["total"]
        else "**не спостерігалося** (0 із 0)"
    )

    # Динамічне порівняння з незалежним базовим звітом dora-summary.md (Етап 2)
    freq_matches = (
        abs(s["deployment_freq_per_day"] - MANUAL_BASELINE["deployment_freq_per_day"])
        < 0.05
        and c["success"] == MANUAL_BASELINE["success_deployments"]
    )
    if freq_matches:
        freq_comparison = (
            f"Повний збіг для **{c['success']} зелених** розгортань "
            f"(зріз усіх {c['total']} злитих одиниць: "
            f"`{m2['deployment_freq_per_day']:.1f} / день`, "
            f"`{m2['deployment_freq_per_week']:.1f} / тиждень`)."
        )
    else:
        freq_comparison = (
            f"Розбіжність: {s['deployment_freq_per_day']:.1f} vs "
            f"{MANUAL_BASELINE['deployment_freq_per_day']:.1f} / день "
            f"({c['success']} зелених розгортань у поточній вибірці проти "
            f"{MANUAL_BASELINE['success_deployments']} у базовому звіті за "
            f"{metrics['period_days']} днів; зріз усіх {c['total']} одиниць: "
            f"`{m2['deployment_freq_per_day']:.1f} / день`)."
        )

    lead_time_matches = (
        abs(s["lead_time_median_s"] - 1462) <= 1
        and abs(s["lead_time_mean_s"] - MANUAL_BASELINE["lead_time_mean_s"]) <= 1
        and abs(s["lead_time_p75_s"] - MANUAL_BASELINE["lead_time_p75_s"]) <= 1
        and c["success"] == MANUAL_BASELINE["success_deployments"]
    )
    if lead_time_matches:
        lead_time_comparison = (
            "Різниця `1 с` на медіані через округлення парної вибірки "
            "`(1228 + 1697) / 2 = 1462.5 с`: `24 хв 23 с` угору проти "
            "банківського `round()` у Python (`24 хв 22 с`); середнє й P75 "
            f"збігаються, а для всіх {c['total']} одиниць медіана "
            f"`{_format_duration(m2['lead_time_median_s'])}`."
        )
    else:
        lead_time_comparison = (
            f"Розбіжність: медіана {_format_duration(s['lead_time_median_s'])} vs "
            f"{_format_duration(MANUAL_BASELINE['lead_time_median_s'])}, середнє "
            f"{_format_duration(s['lead_time_mean_s'])} vs "
            f"{_format_duration(MANUAL_BASELINE['lead_time_mean_s'])} "
            f"({c['success']} зелених розгортань у вибірці; для всіх {c['total']} "
            f"одиниць медіана `{_format_duration(m2['lead_time_median_s'])}`)."
        )

    cfr_matches = (
        abs(s["cfr_no_cancelled_pct"] - MANUAL_BASELINE["cfr_no_cancelled_pct"]) < 0.05
        and abs(s["cfr_with_cancelled_pct"] - MANUAL_BASELINE["cfr_with_cancelled_pct"])
        < 0.05
        and c["failure"] == MANUAL_BASELINE["failure_units"]
        and c["success"] == MANUAL_BASELINE["success_deployments"]
        and c["cancelled"] == MANUAL_BASELINE["cancelled_units"]
    )
    if cfr_matches:
        cfr_comparison = (
            f"Формула `{c['failure']} / ({c['success']} + {c['failure']})` "
            f"і консервативна `({c['failure']} + {c['cancelled']}) / {c['total']}` "
            "збігаються."
        )
    else:
        cfr_comparison = (
            f"Розбіжність: {s['cfr_no_cancelled_pct']:.1f}% vs "
            f"{MANUAL_BASELINE['cfr_no_cancelled_pct']:.1f}% (поточна вибірка містить "
            f"{c['failure']} ❌, {c['success']} ✅, {c['cancelled']} ⚠️; "
            f"базовий звіт: {MANUAL_BASELINE['failure_units']} ❌, "
            f"{MANUAL_BASELINE['success_deployments']} ✅)."
        )

    recovery_matches = (
        not s.get("open_incident")
        and c["failure"] == MANUAL_BASELINE["failure_units"]
        and len(s["incident_recoveries_s"]) == 1
        and abs(s["per_failure_median_s"] - MANUAL_BASELINE["per_failure_median_s"])
        <= 1
        and abs(s["per_failure_mean_s"] - MANUAL_BASELINE["per_failure_mean_s"]) <= 1
        and s["incident_recoveries_s"][0] == MANUAL_BASELINE["incident_episode_s"]
    )
    if recovery_matches:
        recovery_comparison = (
            "Обидва показники збігаються до секунди: усі 8 падінь відбулися в одній "
            "серії `Deploy API docs` 30 жовтня перед відновленням у PR #231 "
            "(`15:41:20 UTC`)."
        )
    elif c["failure"] == 0:
        recovery_comparison = (
            "Розбіжність: у поточній вибірці збоїв не зафіксовано, тоді як "
            "базовий звіт містить 8 збоїв із медіаною "
            f"{_format_duration(MANUAL_BASELINE['per_failure_median_s'])}."
        )
    elif not s["incident_recoveries_s"]:
        recovery_comparison = (
            f"Розбіжність: у вибірці зафіксовано {c['failure']} ❌, але жодного "
            "наступного успішного розгортання в межах періоду не відбулося "
            f"(відновлення не завершено; базовий звіт містить 8 збоїв із медіаною "
            f"{_format_duration(MANUAL_BASELINE['per_failure_median_s'])})."
        )
    elif s.get("open_incident"):
        recovery_comparison = (
            f"Розбіжність: по завершених відновленнях медіана {rec_per_fail}, "
            f"середнє {rec_per_fail_mean}, проте наприкінці періоду залишається "
            f"невідновлений інцидент ({s['unresolved_failures']} ❌ з {c['failure']} "
            "без наступного зеленого розгортання)."
        )
    else:
        recovery_comparison = (
            f"Розбіжність: медіана {rec_per_fail} vs "
            f"{_format_duration(MANUAL_BASELINE['per_failure_median_s'])}, середнє "
            f"{rec_per_fail_mean} vs "
            f"{_format_duration(MANUAL_BASELINE['per_failure_mean_s'])} "
            f"({c['failure']} ❌ у вибірці)."
        )

    if c["total"] == 0:
        status_success_rate = "не спостерігалося"
    elif (c["success"] / c["total"]) < 0.90:
        if c["failure"] == 8 and c["success"] == 48:
            status_success_rate = (
                "Нижче орієнтира через серію падінь `Deploy API docs` 30.10"
            )
        else:
            status_success_rate = "Нижче орієнтира 90%"
    else:
        status_success_rate = "У межах орієнтира"

    if s.get("open_incident") and s["incident_recoveries_s"]:
        if max(s["incident_recoveries_s"]) > 3600:
            status_recovery = (
                "Перевищено орієнтир і відновлення очікується "
                "(наявний невідновлений збій наприкінці періоду)"
            )
        else:
            status_recovery = (
                "Відновлення очікується (попередній інцидент закрито, "
                "але новий збій залишається невідновленим)"
            )
    elif s.get("open_incident") or (
        not s["incident_recoveries_s"] and c["failure"] > 0
    ):
        status_recovery = (
            "Відновлення очікується (наявні збої не закрито зеленим розгортанням)"
        )
    elif s["incident_recoveries_s"] and max(s["incident_recoveries_s"]) > 3600:
        status_recovery = "Перевищено (тривалий повторний збій без блокування злиття)"
    elif s["incident_recoveries_s"]:
        status_recovery = "У межах орієнтира"
    else:
        status_recovery = "Збоїв не спостерігалося (main залишався зеленим)"

    if c["total"] == 0:
        status_ci_duration = "не спостерігалося"
    elif b["ci_total_median_s"] <= 600:
        status_ci_duration = "У межах орієнтира"
    else:
        status_ci_duration = "Перевищено орієнтир (понад 10 хв)"

    lines = [
        "# Автоматичний звіт DORA-метрик CI/CD (Бонус 1)",
        "",
        f"- **Репозиторій:** `{DEFAULT_REPO}` (гілка `main`)",
        (
            f"- **Період:** {DEFAULT_SINCE} — {DEFAULT_UNTIL} "
            f"({metrics['period_days']} календарних днів)"
        ),
        (
            f"- **Вхідні дані:** `{c['total']}` одиниць постачання "
            f"(`{c['success']}` ✅, `{c['failure']}` ❌, `{c['cancelled']}` ⚠️) — "
            "[evidence/main-runs-2026-10-30-to-2026-11-13.json]"
            "(evidence/main-runs-2026-10-30-to-2026-11-13.json)"
        ),
        "- **Команда запуску:** `python scripts/calculate_dora_metrics.py`",
        "",
        (
            "## 1. Чотири метрики DORA "
            "(звірка автоматичного розрахунку і `dora-summary.md`)"
        ),
        "",
        (
            "| Метрика DORA | Автоматичний (`calculate_dora_metrics.py`) | "
            "`dora-summary.md` (Етап 2) | Звірка / джерело розбіжності |"
        ),
        "|---|---:|---:|---|",
        (
            f"| Частота розгортань | "
            f"**{s['deployment_freq_per_day']:.1f} / день** "
            f"({s['deployment_freq_per_week']:.1f} / тиждень) | "
            f"**{MANUAL_BASELINE['deployment_freq_per_day']:.1f} / день** "
            f"({MANUAL_BASELINE['deployment_freq_per_week']:.1f} / тиждень) | "
            f"{freq_comparison} |"
        ),
        (
            f"| Час виконання змін | "
            f"медіана **{_format_duration(s['lead_time_median_s'])}**, "
            f"середнє **{_format_duration(s['lead_time_mean_s'])}**, "
            f"P75 **{_format_duration(s['lead_time_p75_s'])}** | "
            f"медіана **{_format_duration(MANUAL_BASELINE['lead_time_median_s'])}**, "
            f"середнє **{_format_duration(MANUAL_BASELINE['lead_time_mean_s'])}**, "
            f"P75 **{_format_duration(MANUAL_BASELINE['lead_time_p75_s'])}** | "
            f"{lead_time_comparison} |"
        ),
        (
            f"| Частка невдалих змін | "
            f"**{s['cfr_no_cancelled_pct']:.1f}%** (без скасованих) / "
            f"**{s['cfr_all_units_pct']:.1f}%** (з {c['total']}) | "
            f"**{MANUAL_BASELINE['cfr_no_cancelled_pct']:.1f}%** (чутливість "
            f"{MANUAL_BASELINE['cfr_with_cancelled_pct']:.1f}%) | "
            f"{cfr_comparison} |"
        ),
        (
            f"| Час відновлення після збою | "
            f"по окремих ❌: медіана **{rec_per_fail}**, "
            f"середнє **{rec_per_fail_mean}**; "
            f"інцидент від першого збою: **{rec_episode}** | "
            f"медіана **{_format_duration(MANUAL_BASELINE['per_failure_median_s'])}**, "
            f"середнє **{_format_duration(MANUAL_BASELINE['per_failure_mean_s'])}** "
            f"(макс. **{_format_duration(MANUAL_BASELINE['incident_episode_s'])}**) | "
            f"{recovery_comparison} |"
        ),
        "",
        "## 2. Відокремлення черги від виконання в часі проходження змін",
        "",
        (
            f"| Компонент (усі {c['total']} одиниць) | Медіана | Середнє | P75 | "
            "Максимум | Частка сумарного Lead Time | "
            "Частка часу CI (`черга + виконання`) |"
        ),
        "|---|---:|---:|---:|---:|---:|---:|",
        (
            f"| До запуску CI (код і рев'ю PR) | — | — | — | — | "
            f"**{b['pre_ci_share_lt_pct']:.2f}%** | — |"
        ),
        (
            f"| Очікування в черзі на раннер | "
            f"**{_format_duration(b['queue_median_s'])}** | "
            f"{_format_duration(b['queue_mean_s'])} | "
            f"{_format_duration(b['queue_p75_s'])} | "
            f"{_format_duration(b['queue_max_s'])} | "
            f"**{b['queue_share_lt_pct']:.2f}%** | "
            f"**{b['queue_share_ci_pct']:.1f}%** |"
        ),
        (
            f"| Виконання завдань CI (`CI` + `Deploy API docs`) | "
            f"**{_format_duration(b['exec_median_s'])}** | "
            f"{_format_duration(b['exec_mean_s'])} | "
            f"{_format_duration(b['exec_p75_s'])} | "
            f"{_format_duration(b['exec_max_s'])} | "
            f"**{b['exec_share_lt_pct']:.2f}%** | "
            f"**{b['exec_share_ci_pct']:.1f}%** |"
        ),
        (
            f"| Повний Change Lead Time ({c['total']} одиниць) | "
            f"**{_format_duration(m2['lead_time_median_s'])}** | "
            f"{_format_duration(m2['lead_time_mean_s'])} | "
            f"{_format_duration(m2['lead_time_p75_s'])} | "
            f"{_format_duration(m2['lead_time_max_s'])} | "
            f"100.00% | — |"
        ),
        "",
        f"Для {c['success']} зелених розгортань медіанна черга становить "
        f"**{_format_duration(b['green_queue_median_s'])}** (середнє "
        f"{_format_duration(b['green_queue_mean_s'])}, P75 "
        f"{_format_duration(b['green_queue_p75_s'])}), а медіанне виконання — "
        f"**{_format_duration(b['green_exec_median_s'])}** (середнє "
        f"{_format_duration(b['green_exec_mean_s'])}, P75 "
        f"{_format_duration(b['green_exec_p75_s'])}); частки повного Lead Time: "
        f"до CI `{b['green_pre_ci_share_lt_pct']:.2f}%`, черга "
        f"`{b['green_queue_share_lt_pct']:.2f}%` "
        f"(`{b['green_queue_share_ci_pct']:.2f}%` CI), виконання "
        f"`{b['green_exec_share_lt_pct']:.2f}%` "
        f"(`{b['green_exec_share_ci_pct']:.2f}%` CI).",
        "",
        "## 3. Звірка з орієнтирами телеметрії CI (CircleCI 2025/2026)",
        "",
        "| Показник | Наш результат | Орієнтир CircleCI | Статус |",
        "|---|---:|---:|---|",
        (
            f"| Частка успішних запусків на `main` | "
            f"{success_rate_cell} | 90% | "
            f"{status_success_rate} |"
        ),
        (
            f"| Повернення `main` до зеленого стану | **{rec_episode}** | "
            f"до 60 хв | {status_recovery} |"
        ),
        (
            f"| Тривалість запуску workflow (медіана `черга + виконання`) | "
            f"**{_format_duration(b['ci_total_median_s'])}** | до 10 хв | "
            f"{status_ci_duration} |"
        ),
        "",
        "> ### Нотатка «Використання ШІ»",
        "> - **Інструмент:** Antigravity (агентний AI-асистент у VS Code).",
        (
            "> - **Автор перевірки:** Євгеній Остапенко "
            "(Аналітик даних CI/CD — Бонус 1)."
        ),
        (
            "> - **Що згенеровано:** структура скрипта "
            "`scripts/calculate_dora_metrics.py` та шаблон Markdown-звіту."
        ),
        (
            "> - **Що перевірено / виправлено вручну:** формули DORA "
            "(строгі 48 зелених розгортань vs усі 60 одиниць), відокремлення "
            "`queue` від `execution`, розбіжності з ручним Етапом 2 та "
            "відповідність усіх 60 одиниць доказів у "
            "`docs/ci-cd/evidence/main-runs-2026-10-30-to-2026-11-13.json` "
            "реальним відповідям GitHub Actions API."
        ),
        "",
    ]
    return "\n".join(lines)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Автоматичний підрахунок 4 метрик DORA (Лаб 10, Бонус 1)."
    )
    parser.add_argument(
        "--fetch-github",
        action="store_true",
        help="Отримати свіжі запуски з GitHub Actions REST API",
    )
    args = parser.parse_args()

    start_d = datetime.strptime(DEFAULT_SINCE, "%Y-%m-%d").date()
    end_d = datetime.strptime(DEFAULT_UNTIL, "%Y-%m-%d").date()
    period_days = (end_d - start_d).days + 1

    if args.fetch_github:
        units, raw_runs = fetch_units_from_github()
        save_evidence(units, raw_runs, period_days)
    else:
        units = load_units_from_evidence()

    metrics = compute_metrics(units, period_days)
    report = render_markdown(metrics)
    DEFAULT_OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    with open(DEFAULT_OUTPUT, "w", encoding="utf-8") as out_file:
        out_file.write(report)

    s = metrics["strict"]
    b = metrics["breakdown"]
    recovery_text = _format_incident_recoveries(
        s, failure_count=metrics["counts"]["failure"]
    )
    print(f"[OK] Автоматичний звіт DORA збережено: {DEFAULT_OUTPUT}")
    print(
        f"     Розгортання (зелені): {metrics['counts']['success']} "
        f"({s['deployment_freq_per_day']:.1f}/день) | "
        f"Lead Time медіана: {_format_duration(s['lead_time_median_s'])}"
    )
    print(
        f"     Черга (мед./сер.): {_format_duration(b['queue_median_s'])} / "
        f"{_format_duration(b['queue_mean_s'])} | "
        f"Виконання (мед./сер.): {_format_duration(b['exec_median_s'])} / "
        f"{_format_duration(b['exec_mean_s'])}"
    )
    print(
        f"     CFR (без скасованих): {s['cfr_no_cancelled_pct']:.1f}% | "
        f"Відновлення інциденту: {recovery_text}"
    )


if __name__ == "__main__":
    main()
