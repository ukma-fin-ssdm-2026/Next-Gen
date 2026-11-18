import json
from datetime import datetime, timezone
from pathlib import Path
import sys
from typing import Any

import pytest

from scripts import calculate_dora_metrics as cdm


class _FakeResponse:
    def __init__(self, payload: Any, ok: bool = True) -> None:
        self._payload = payload
        self.ok = ok

    def raise_for_status(self) -> None:
        if not self.ok:
            raise RuntimeError("HTTP error")

    def json(self) -> Any:
        return self._payload


def _make_github_run(
    run_id: int,
    name: str,
    sha: str,
    pr_number: int,
    created_at: str,
    started_at: str,
    updated_at: str,
    conclusion: str = "success",
    workflow_id: int = 1,
) -> dict[str, Any]:
    return {
        "id": run_id,
        "name": name,
        "workflow_id": workflow_id,
        "head_sha": sha,
        "status": "completed",
        "conclusion": conclusion,
        "run_attempt": 1,
        "event": "push",
        "created_at": created_at,
        "run_started_at": started_at,
        "updated_at": updated_at,
        "display_title": f"Merge pull request #{pr_number} from ukma/feat",
        "html_url": f"https://github.com/example/repo/actions/runs/{run_id}",
    }


def _install_mock_github(
    monkeypatch: pytest.MonkeyPatch,
    runs: list[dict[str, Any]],
    jobs_by_run: dict[int, list[dict[str, str]]],
    first_commit_by_pr: dict[int, str],
) -> None:
    def fake_get(url: str, **kwargs: Any) -> _FakeResponse:
        if url.endswith("/actions/runs"):
            page = kwargs.get("params", {}).get("page", 1)
            return _FakeResponse({"workflow_runs": runs if page == 1 else []})
        if "/actions/runs/" in url and url.endswith("/jobs"):
            run_id = int(url.split("/actions/runs/")[1].split("/")[0])
            return _FakeResponse({"jobs": jobs_by_run[run_id]})
        if "/pulls/" in url and url.endswith("/commits"):
            pr_num = int(url.split("/pulls/")[1].split("/")[0])
            dt = first_commit_by_pr[pr_num]
            return _FakeResponse([{"commit": {"author": {"date": dt}}}])
        raise AssertionError(f"Unexpected URL requested: {url}")

    monkeypatch.setattr(cdm.requests, "get", fake_get)


def test_fetch_units_filters_window_by_job_completed_at(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """[TP-058]
    Фільтрує вікно за `completed_at` завдань, навіть коли `updated_at` пізніше.
    """
    monkeypatch.setattr(cdm, "DEFAULT_EVIDENCE", tmp_path / "missing-evidence.json")
    sha_in = "aaaaaaa111111111111111111111111111111111"
    sha_out = "bbbbbbb222222222222222222222222222222222"

    runs = [
        _make_github_run(
            10,
            "CI",
            sha_in,
            101,
            "2026-11-13T23:55:00Z",
            "2026-11-13T23:55:10Z",
            "2026-11-14T00:00:00Z",
            workflow_id=360541177,
        ),
        _make_github_run(
            11,
            "Deploy API docs",
            sha_in,
            101,
            "2026-11-13T23:55:00Z",
            "2026-11-13T23:55:15Z",
            "2026-11-14T00:00:00Z",
            workflow_id=377505064,
        ),
        _make_github_run(
            12,
            "CI",
            sha_out,
            102,
            "2026-11-13T23:55:00Z",
            "2026-11-13T23:55:10Z",
            "2026-11-14T00:00:02Z",
            workflow_id=360541177,
        ),
    ]
    jobs_by_run = {
        10: [
            {
                "started_at": "2026-11-13T23:55:10Z",
                "completed_at": "2026-11-13T23:59:59Z",
            }
        ],
        11: [
            {
                "started_at": "2026-11-13T23:55:15Z",
                "completed_at": "2026-11-13T23:58:00Z",
            }
        ],
        12: [
            {
                "started_at": "2026-11-13T23:55:10Z",
                "completed_at": "2026-11-14T00:00:01Z",
            }
        ],
    }
    first_commits = {
        101: "2026-11-13T23:40:00Z",
        102: "2026-11-13T23:45:00Z",
    }
    _install_mock_github(monkeypatch, runs, jobs_by_run, first_commits)

    units, raw_runs = cdm.fetch_units_from_github()

    assert [u.full_sha for u in units] == [sha_in]
    assert units[0].completed_at == datetime(
        2026, 11, 13, 23, 59, 59, tzinfo=timezone.utc
    )
    assert len(raw_runs) == 2


def test_main_fetch_github_persists_evidence_for_offline_replay(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """[TP-058]
    `--fetch-github` оновлює файл доказів для відтворюваного офлайн-запуску.
    """
    evidence_path = tmp_path / "evidence.json"
    output_path = tmp_path / "report.md"
    evidence_path.write_text(
        json.dumps(
            {
                "metadata": {"delivery_units_count": 1},
                "delivery_units": [
                    {
                        "unit_number": 1,
                        "commit_sha": "deadbee",
                        "full_sha": "deadbeef" * 5,
                        "pr_number": 1,
                        "pr_url": "https://github.com/example/repo/pull/1",
                        "first_commit_at": "2026-10-30T01:00:00Z",
                        "completed_at": "2026-10-30T02:00:00Z",
                        "queue_seconds": 5,
                        "execution_seconds": 50,
                        "lead_time_seconds": 3600,
                        "status": "failure",
                        "note": "stale",
                        "workflow_runs": [],
                    }
                ],
                "github_runs_raw": [],
            }
        ),
        encoding="utf-8",
    )
    monkeypatch.setattr(cdm, "DEFAULT_EVIDENCE", evidence_path)
    monkeypatch.setattr(cdm, "DEFAULT_OUTPUT", output_path)

    sha1 = "1111111aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"
    sha2 = "2222222bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb"
    runs = [
        _make_github_run(
            1,
            "CI",
            sha1,
            201,
            "2026-11-01T10:00:00Z",
            "2026-11-01T10:00:05Z",
            "2026-11-01T10:01:05Z",
        ),
        _make_github_run(
            2,
            "Deploy API docs",
            sha1,
            201,
            "2026-11-01T10:00:00Z",
            "2026-11-01T10:00:05Z",
            "2026-11-01T10:00:45Z",
        ),
        _make_github_run(
            3,
            "CI",
            sha2,
            202,
            "2026-11-02T12:00:00Z",
            "2026-11-02T12:00:10Z",
            "2026-11-02T12:01:10Z",
        ),
        _make_github_run(
            4,
            "Deploy API docs",
            sha2,
            202,
            "2026-11-02T12:00:00Z",
            "2026-11-02T12:00:10Z",
            "2026-11-02T12:00:50Z",
        ),
    ]
    jobs_by_run = {
        1: [
            {
                "started_at": "2026-11-01T10:00:05Z",
                "completed_at": "2026-11-01T10:01:05Z",
            }
        ],
        2: [
            {
                "started_at": "2026-11-01T10:00:05Z",
                "completed_at": "2026-11-01T10:00:45Z",
            }
        ],
        3: [
            {
                "started_at": "2026-11-02T12:00:10Z",
                "completed_at": "2026-11-02T12:01:10Z",
            }
        ],
        4: [
            {
                "started_at": "2026-11-02T12:00:10Z",
                "completed_at": "2026-11-02T12:00:50Z",
            }
        ],
    }
    first_commits = {201: "2026-11-01T09:50:00Z", 202: "2026-11-02T11:45:00Z"}
    _install_mock_github(monkeypatch, runs, jobs_by_run, first_commits)

    monkeypatch.setattr(sys, "argv", ["calculate_dora_metrics.py", "--fetch-github"])
    cdm.main()
    live_report = output_path.read_text(encoding="utf-8")
    saved_payload = json.loads(evidence_path.read_text(encoding="utf-8"))

    assert saved_payload["metadata"]["delivery_units_count"] == 2
    assert len(saved_payload["delivery_units"]) == 2
    assert len(saved_payload["github_runs_raw"]) == 4

    def fail_if_called() -> Any:
        raise AssertionError("Offline replay should not call fetch_units_from_github")

    monkeypatch.setattr(cdm, "fetch_units_from_github", fail_if_called)
    monkeypatch.setattr(sys, "argv", ["calculate_dora_metrics.py"])
    cdm.main()
    replay_report = output_path.read_text(encoding="utf-8")

    assert replay_report == live_report
    assert "**0.0%** (без скасованих)" in replay_report
    assert "**14.3%** (чутливість 20.0%)" in replay_report


def _make_unit(
    num: int,
    sha: str,
    pr: int,
    start: tuple[int, int, int],
    end: tuple[int, int, int],
    status: str,
    execution_seconds: int = 60,
    queue_seconds: int = 5,
) -> cdm.DeliveryUnit:
    return cdm.DeliveryUnit(
        unit_number=num,
        commit_sha=sha,
        full_sha=sha * 5 + "abcde",
        pr_number=pr,
        pr_url=None,
        first_commit_at=datetime(
            2026, 11, 1, start[0], start[1], start[2], tzinfo=timezone.utc
        ),
        completed_at=datetime(2026, 11, 1, end[0], end[1], end[2], tzinfo=timezone.utc),
        queue_seconds=queue_seconds,
        execution_seconds=execution_seconds,
        status=status,
    )


def test_render_markdown_handles_unresolved_failures_and_breached_duration() -> None:
    """[TP-058] Невідновлені збої та тривалість >10 хв коректно позначаються у звіті."""
    failed_unit = _make_unit(
        1,
        "abc1234",
        301,
        (9, 0, 0),
        (10, 0, 0),
        "failure",
        execution_seconds=1200,
        queue_seconds=0,
    )
    metrics = cdm.compute_metrics([failed_unit], 15)
    report = cdm.render_markdown(metrics)

    assert "Відновлення очікується" in report
    assert "Збоїв не спостерігалося" not in report
    assert "**20 хв** | до 10 хв | Перевищено орієнтир (понад 10 хв)" in report
    assert "**100.0%** (без скасованих)" in report
    assert "**14.3%** (чутливість 20.0%)" in report


def test_compute_metrics_sorts_by_completed_at_for_recovery() -> None:
    """[TP-058]
    Відновлення рахується за хронологією `completed_at`, а не порядком створення.
    """
    failed_first = _make_unit(1, "fail111", 401, (10, 0, 0), (10, 10, 0), "failure")
    green_earlier = _make_unit(2, "succ111", 402, (10, 2, 0), (10, 5, 0), "success")
    green_later = _make_unit(3, "succ222", 403, (10, 15, 0), (10, 25, 0), "success")

    unresolved = cdm.compute_metrics([failed_first, green_earlier], 15)["strict"]
    assert unresolved["incident_recoveries_s"] == []
    assert unresolved["per_failure_median_s"] == 0
    assert unresolved["open_incident"] is True
    assert unresolved["unresolved_failures"] == 1

    resolved = cdm.compute_metrics([failed_first, green_earlier, green_later], 15)[
        "strict"
    ]
    assert resolved["incident_recoveries_s"] == [900]
    assert resolved["per_failure_median_s"] == 900
    assert resolved["open_incident"] is False
    assert resolved["unresolved_failures"] == 0


def test_render_markdown_tracks_open_incident_after_earlier_recovery() -> None:
    """[TP-058]
    Попереднє швидке відновлення не приховує відкритий інцидент у кінці періоду.
    """
    units = [
        _make_unit(1, "fail111", 501, (9, 50, 0), (10, 0, 0), "failure"),
        _make_unit(2, "succ111", 502, (9, 55, 0), (10, 1, 0), "success"),
        _make_unit(3, "fail222", 503, (10, 2, 0), (10, 5, 0), "failure"),
    ]
    metrics = cdm.compute_metrics(units, 15)
    assert metrics["strict"]["incident_recoveries_s"] == [60]
    assert metrics["strict"]["open_incident"] is True
    assert metrics["strict"]["unresolved_failures"] == 1

    report = cdm.render_markdown(metrics)
    recovery_telemetry_line = next(
        line
        for line in report.splitlines()
        if line.startswith("| Повернення `main` до зеленого стану |")
    )
    assert "1 хв" in recovery_telemetry_line
    assert "невідновлений інцидент" in recovery_telemetry_line
    assert (
        "Відновлення очікується (попередній інцидент закрито, "
        "але новий збій залишається невідновленим)"
    ) in recovery_telemetry_line
    assert "У межах орієнтира" not in recovery_telemetry_line
    assert "залишається невідновлений інцидент (1 ❌ з 2" in report
