from datetime import UTC, date, datetime

from ws.taskmodel import Status, Task
from ws.taskstatus import evaluate

TODAY = date(2026, 10, 27)


def make_task(key: str, status: Status, updated: datetime | None = None) -> Task:
    return Task(
        ref=key,
        key=key,
        title="Titulo de exemplo",
        url=f"https://example.atlassian.net/browse/{key}",
        status=status,
        epic_key=None,
        epic_title=None,
        requested_by_other=False,
        updated=updated or datetime(2026, 10, 26, 9, 0, tzinfo=UTC),
    )


def make_activity(**overrides) -> dict:
    activity = {
        "window": {"since": "2026-10-26", "until": "2026-10-27"},
        "commits": [],
        "branches": [],
        "prs": [],
        "last_activity": {},
        "next_steps": [],
        "warnings": [],
    }
    activity.update(overrides)
    return activity


def make_pr(number: int, keys: list[str], merged_at: str | None) -> dict:
    return {
        "repo": "app",
        "number": number,
        "title": "Ajuste",
        "state": "merged" if merged_at else "open",
        "merged_at": merged_at,
        "url": f"https://example.com/app/pull/{number}",
        "keys": keys,
    }


def test_todo_with_commit_suggests_in_progress():
    activity = make_activity(
        commits=[
            {
                "repo": "app",
                "sha": "abc123",
                "date": "2026-10-26",
                "subject": "ajuste",
                "keys": ["TS-101"],
            }
        ]
    )
    result = evaluate([make_task("TS-101", Status.TODO)], activity, TODAY, 3)
    assert result["suggestions"] == [
        {
            "key": "TS-101",
            "from": "todo",
            "to": "in_progress",
            "rule": "R1",
            "evidence": "abc123",
        }
    ]


def test_todo_with_branch_suggests_in_progress():
    activity = make_activity(
        branches=[{"repo": "app", "name": "feature/TS-101-x", "keys": ["TS-101"]}]
    )
    result = evaluate([make_task("TS-101", Status.TODO)], activity, TODAY, 3)
    assert result["suggestions"][0]["evidence"] == "feature/TS-101-x"


def test_todo_with_only_another_key_commit_suggests_nothing():
    activity = make_activity(
        commits=[
            {
                "repo": "app",
                "sha": "abc123",
                "date": "2026-10-26",
                "subject": "ajuste",
                "keys": ["TS-999"],
            }
        ]
    )
    result = evaluate([make_task("TS-101", Status.TODO)], activity, TODAY, 3)
    assert result == {"suggestions": [], "stuck": []}


def test_in_progress_with_merged_pr_suggests_validation():
    activity = make_activity(prs=[make_pr(7, ["TS-101"], "2026-10-26T12:00:00Z")])
    result = evaluate([make_task("TS-101", Status.IN_PROGRESS)], activity, TODAY, 3)
    assert result["suggestions"] == [
        {
            "key": "TS-101",
            "from": "in_progress",
            "to": "validation",
            "rule": "R2",
            "evidence": "app#7",
        }
    ]


def test_in_progress_with_open_pr_suggests_nothing():
    activity = make_activity(
        prs=[make_pr(7, ["TS-101"], None)], last_activity={"TS-101": "2026-10-26"}
    )
    result = evaluate([make_task("TS-101", Status.IN_PROGRESS)], activity, TODAY, 3)
    assert result == {"suggestions": [], "stuck": []}


def test_one_merged_pr_with_two_keys_suggests_both():
    activity = make_activity(prs=[make_pr(7, ["TS-101", "TS-102"], "2026-10-26T12:00:00Z")])
    tasks = [
        make_task("TS-101", Status.IN_PROGRESS),
        make_task("TS-102", Status.IN_PROGRESS),
    ]
    result = evaluate(tasks, activity, TODAY, 3)
    assert [(s["key"], s["to"], s["evidence"]) for s in result["suggestions"]] == [
        ("TS-101", "validation", "app#7"),
        ("TS-102", "validation", "app#7"),
    ]


def test_in_progress_without_activity_and_old_update_is_stuck():
    old = datetime(2026, 10, 20, 9, 0, tzinfo=UTC)
    result = evaluate([make_task("TS-101", Status.IN_PROGRESS, old)], make_activity(), TODAY, 3)
    assert result["stuck"] == [{"key": "TS-101", "last_activity": None}]


def test_in_progress_with_commit_in_window_is_not_stuck():
    old = datetime(2026, 10, 20, 9, 0, tzinfo=UTC)
    activity = make_activity(last_activity={"TS-101": "2026-10-26"})
    result = evaluate([make_task("TS-101", Status.IN_PROGRESS, old)], activity, TODAY, 3)
    assert result["stuck"] == []


def test_in_progress_updated_on_the_cutoff_day_is_not_stuck():
    cutoff = datetime(2026, 10, 22, 9, 0, tzinfo=UTC)
    result = evaluate([make_task("TS-101", Status.IN_PROGRESS, cutoff)], make_activity(), TODAY, 3)
    assert result["stuck"] == []
