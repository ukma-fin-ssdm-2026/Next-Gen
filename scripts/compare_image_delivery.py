"""Compare CI and GHCR delivery on the same cohort of main commits."""

import argparse
from collections.abc import Iterator
from datetime import date, datetime, timedelta, timezone
import json
import os
import re
from statistics import mean, median
from urllib.error import HTTPError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

PUBLISH_TITLE = re.compile(r"Publish ([0-9a-f]{40}) from CI #(\d+)")
MERGE_TITLE = re.compile(r"Merge pull request #(\d+) from ")
FAILURES = {"failure", "timed_out", "startup_failure", "action_required"}
DEFAULT_REPO = "ukma-fin-ssdm-2026/Next-Gen"


def api(repo, path, **query):
    url = f"https://api.github.com/repos/{repo}/{path}?{urlencode(query)}"
    request = Request(url, headers={"Accept": "application/vnd.github+json"})
    token = os.getenv("GH_TOKEN") or os.getenv("GITHUB_TOKEN")
    if token:
        request.add_header("Authorization", f"Bearer {token}")
    with urlopen(request, timeout=20) as response:  # nosec B310: HTTPS GitHub API
        return json.load(response)


def pages(repo, path, key, **query) -> Iterator[dict]:
    page = 1
    while True:
        result = api(repo, path, per_page=100, page=page, **query)
        items = result[key] if key else result
        yield from items
        if len(items) < 100:
            return
        page += 1


def timestamp(value):
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def runs(repo, workflow, start, end, event):
    return pages(
        repo,
        f"actions/workflows/{workflow}/runs",
        "workflow_runs",
        branch="main",
        event=event,
        created=f"{start}..{end - timedelta(days=1)}",
    )


def first_commit(repo, run):
    match = MERGE_TITLE.match(run["display_title"])
    if match:
        number = match[1]
        path = f"pulls/{number}"
        pull = api(repo, path)
        if pull["merge_commit_sha"] != run["head_sha"] or pull["base"]["ref"] != "main":
            raise ValueError(f"PR #{number} does not match the source CI commit")
        commits = pages(repo, f"{path}/commits", None)
        try:
            return min(timestamp(item["commit"]["author"]["date"]) for item in commits)
        except ValueError as error:
            raise ValueError(f"PR #{number} has no authored commit") from error
    commit = api(repo, f"commits/{run['head_sha']}")
    if len(commit["parents"]) > 1:
        raise ValueError(f"Could not identify the PR for merge {run['head_sha']}")
    return timestamp(commit["commit"]["author"]["date"])


def observed(repo, run):
    conclusion = run["conclusion"]
    if conclusion != "success" and conclusion not in FAILURES:
        return None
    jobs = pages(repo, f"actions/runs/{run['id']}/jobs", "jobs", filter="latest")
    finishes = [
        timestamp(job["completed_at"])
        for job in jobs
        if job["completed_at"] and job["conclusion"] != "skipped"
    ]
    if not finishes:
        # GitHub can reject workflow startup before creating any job.
        return timestamp(run["updated_at"])
    return max(finishes)


def linked_publications(repo, start, today, sources):
    try:
        candidates = list(
            runs(
                repo,
                "publish-image.yml",
                start,
                today + timedelta(days=1),
                "workflow_run",
            )
        )
    except HTTPError as error:
        if error.code != 404:
            raise
        return {}
    publication = {}
    for run in sorted(candidates, key=lambda item: item["id"]):
        match = PUBLISH_TITLE.fullmatch(run["display_title"])
        if not match:
            continue
        sha, source_id = match[1], int(match[2])
        source = sources.get(source_id)
        if source and source["head_sha"] == sha and run["conclusion"] != "skipped":
            publication[source_id] = run
    return publication


def format_intervals(seconds):
    if not seconds:
        return "—"
    return f"{median(seconds) / 60:.2f} / {mean(seconds) / 60:.2f}"


def summarize(results, days):
    timeline = sorted(results, key=lambda item: item[0])
    lead, recovery, failures = [], [], []
    failed = 0
    for finished, good, authored in timeline:
        if good:
            lead.append((finished - authored).total_seconds())
            recovery.extend(
                (finished - failure).total_seconds() for failure in failures
            )
            failures.clear()
        else:
            failed += 1
            failures.append(finished)
    if not timeline:
        return ["—"] * 4
    return [
        f"{len(lead)} / {7 * len(lead) / days:.2f}",
        format_intervals(lead),
        f"{failed}/{len(timeline)} ({failed / len(timeline):.1%})",
        f"{format_intervals(recovery)} ({len(failures)} без відновлення)",
    ]


def render(repo, start, end, today):
    # One unit per SHA. A GitHub rerun updates the conclusion of the same run.
    source_by_sha = {
        run["head_sha"]: run
        for run in sorted(
            runs(repo, "ci.yml", start, end, "push"), key=lambda item: item["id"]
        )
    }
    sources = {run["id"]: run for run in source_by_sha.values()}
    publications = linked_publications(repo, start, today, sources)
    ci_results, image_results, evidence = [], [], []
    gated, awaiting = 0, 0
    for run in sources.values():
        finish = observed(repo, run)
        successful = run["conclusion"] == "success"
        if finish is not None:
            authored = first_commit(repo, run) if successful else None
            ci_results.append((finish, successful, authored))
        if successful:
            image = publications.get(run["id"])
            image_finish = observed(repo, image) if image else None
            if image_finish is not None:
                image_results.append(
                    (image_finish, image["conclusion"] == "success", authored)
                )
            else:
                awaiting += 1
        else:
            image = None
            gated += 1
        image_evidence = (
            f"[{image['id']}]({image['html_url']}) "
            f"({image['conclusion'] or image['status']})"
            if image
            else "—"
        )
        evidence.append(
            f"| `{run['head_sha'][:7]}` | [{run['id']}]({run['html_url']}) "
            f"({run['conclusion'] or run['status']}) | {image_evidence} |"
        )

    rows = [
        "# Порівняння CI та публікацій GHCR",
        "",
        f"Когорта CI за UTC: {start} включно — {end} виключно. Дата зрізу: {today}.",
        f"У когорті {len(sources)} SHA. Без зеленого CI: {gated}. "
        f"Із зеленим CI без завершеної спроби публікації: {awaiting}.",
        "",
        "| Метрика | CI на main | Публікація образу |",
        "|---|---:|---:|",
    ]
    labels = [
        "Успішні розгортання / за тиждень",
        "Час змін (хв), медіана / середнє",
        "Частка невдалих змін",
        "Час відновлення (хв), медіана / середнє",
    ]
    days = (end - start).days
    for label, ci, image in zip(
        labels, summarize(ci_results, days), summarize(image_results, days)
    ):
        rows.append(f"| {label} | {ci} | {image} |")
    rows.extend(("", "| SHA | CI | GHCR |", "|---|---|---|", *evidence))
    return "\n".join(rows)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo", default=DEFAULT_REPO)
    parser.add_argument(
        "--start", type=date.fromisoformat, required=True, help="UTC, inclusive"
    )
    parser.add_argument(
        "--end", type=date.fromisoformat, required=True, help="UTC, exclusive"
    )
    args = parser.parse_args()
    if args.start >= args.end:
        parser.error("--end must be after --start")
    if not re.fullmatch(r"[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+", args.repo):
        parser.error("--repo must have the form owner/name")
    try:
        report = render(
            args.repo, args.start, args.end, datetime.now(timezone.utc).date()
        )
    except HTTPError as error:
        if error.code == 403 and error.headers.get("X-RateLimit-Remaining") == "0":
            parser.exit(1, "GitHub API rate limit reached. Set GH_TOKEN and retry.\n")
        raise
    print(report)


if __name__ == "__main__":
    main()
