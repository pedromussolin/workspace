from datetime import date, datetime

import pytest

from ws.standupsummary import build_summary
from ws.taskmodel import Status, Task

TODAY = date(2026, 11, 3)
WINDOW = {"since": "2026-10-26", "until": "2026-11-01", "kind": "period"}


def make_task(
    key: str,
    status: Status = Status.IN_PROGRESS,
    epic: str | None = None,
    changed: str | None = None,
    updated: str = "2026-10-30T12:00:00+00:00",
) -> Task:
    return Task(
        ref=f"jira:{key}",
        key=key,
        title=f"Título {key}",
        url=f"https://example.atlassian.net/browse/{key}",
        status=status,
        epic_key=epic,
        epic_title=f"Épico {epic}" if epic else None,
        requested_by_other=False,
        updated=datetime.fromisoformat(updated),
        status_changed=datetime.fromisoformat(changed) if changed else None,
    )


def make_commit(key: str | None, day: str, subject: str | None = None, repo: str = "app") -> dict:
    return {
        "repo": repo,
        "sha": f"{abs(hash((key, day, subject))):040x}"[:40],
        "date": day,
        "subject": subject or f"{key} trabalho em {day}",
        "keys": [key] if key else [],
    }


def make_pr(
    number: int,
    key: str,
    state: str = "merged",
    base: str = "master",
    merged: str | None = "2026-10-28T12:00:00Z",
    repo: str = "app",
) -> dict:
    return {
        "repo": repo,
        "number": number,
        "title": f"{key} entrega {number}",
        "state": state,
        "base": base,
        "created_at": "2026-10-27T12:00:00Z",
        "closed_at": merged,
        "merged_at": merged if state == "merged" else None,
        "updated_at": merged or "2026-10-28T12:00:00Z",
        "url": f"https://example.com/{repo}/pull/{number}",
        "keys": [key],
    }


def make_activity(**overrides) -> dict:
    activity = {
        "window": WINDOW,
        "commits": [],
        "branches": [],
        "prs": [],
        "last_activity": {},
        "next_steps": [],
        "warnings": [],
    }
    activity.update(overrides)
    return activity


def summarize(activity, tasks=None, top=None, stale=3):
    return build_summary(activity, tasks, TODAY, stale, top)


def entries(summary) -> dict:
    return {task["key"]: task for theme in summary["themes"] for task in theme["tasks"]}


def test_groups_by_epic_ordered_by_activity():
    commits = [
        make_commit("TS-1", "2026-10-26"),
        make_commit("TS-2", "2026-10-26"),
        make_commit("TS-2", "2026-10-27"),
        make_commit("TS-2", "2026-10-28"),
        make_commit("TS-3", "2026-10-27"),
    ]
    tasks = [
        make_task("TS-1", epic="TS-100"),
        make_task("TS-2", epic="TS-200"),
        make_task("TS-3", epic="TS-200"),
    ]
    summary = summarize(make_activity(commits=commits), tasks)
    assert [theme["key"] for theme in summary["themes"]] == ["TS-200", "TS-100"]
    assert summary["themes"][0]["title"] == "Épico TS-200"
    assert [task["key"] for task in summary["themes"][0]["tasks"]] == ["TS-2", "TS-3"]


def test_cards_without_epic_go_to_sem_epico():
    commits = [make_commit("TS-1", "2026-10-26"), make_commit("TS-9", "2026-10-26")]
    summary = summarize(make_activity(commits=commits), [make_task("TS-1")])
    assert [theme["title"] for theme in summary["themes"]] == ["Sem épico"]
    assert summary["themes"][0]["key"] is None
    assert set(entries(summary)) == {"TS-1", "TS-9"}


def test_task_fields():
    commits = [
        make_commit("TS-1", "2026-10-26", "TS-1 primeiro"),
        make_commit("TS-1", "2026-10-26", "TS-1 segundo"),
        make_commit("TS-1", "2026-10-29", "TS-1 terceiro"),
    ]
    prs = [make_pr(12, "TS-1", base="release")]
    summary = summarize(make_activity(commits=commits, prs=prs), [make_task("TS-1")])
    task = entries(summary)["TS-1"]
    assert task["title"] == "Título TS-1"
    assert task["status"] == "in_progress"
    assert task["url"] == "https://example.atlassian.net/browse/TS-1"
    assert (task["commits"], task["active_days"]) == (3, 2)
    assert (task["first_day"], task["last_day"]) == ("2026-10-26", "2026-10-29")
    assert task["subjects"][0] == "TS-1 terceiro"
    assert task["prs"] == [
        {
            "ref": "app#12",
            "state": "merged",
            "base": "release",
            "merged": "2026-10-28",
            "title": "TS-1 entrega 12",
        }
    ]


def test_subjects_are_capped_at_five():
    commits = [make_commit("TS-1", f"2026-10-{26 + i % 3}", f"TS-1 passo {i}") for i in range(8)]
    task = entries(summarize(make_activity(commits=commits)))["TS-1"]
    assert len(task["subjects"]) == 5
    assert task["commits"] == 8


def test_outcome_production_merged_into_default_branch():
    commits = [make_commit("TS-1", "2026-10-27")]
    prs = [make_pr(12, "TS-1", base="master")]
    task = entries(summarize(make_activity(commits=commits, prs=prs), [make_task("TS-1")]))["TS-1"]
    assert task["outcome"] == "production"
    assert task["evidence"] == "PR app#12 merged into master on 2026-10-28"
    main = entries(summarize(make_activity(prs=[make_pr(5, "TS-2", base="main")])))["TS-2"]
    assert main["outcome"] == "production"


def test_outcome_homologation_other_base_or_status():
    other_base = [make_pr(13, "TS-1", base="release")]
    task = entries(summarize(make_activity(prs=other_base), [make_task("TS-1")]))["TS-1"]
    assert task["outcome"] == "homologation"
    assert task["evidence"] == "PR app#13 merged into release on 2026-10-28"
    for status in (Status.VALIDATION, Status.READY_DEPLOY):
        commits = [make_commit("TS-2", "2026-10-27")]
        card = make_task("TS-2", status)
        found = entries(summarize(make_activity(commits=commits), [card]))["TS-2"]
        assert found["outcome"] == "homologation"
        assert status.value in found["evidence"]


def test_outcome_review_open_pr():
    prs = [make_pr(14, "TS-1", state="open", merged=None)]
    commits = [make_commit("TS-1", "2026-10-27")]
    task = entries(summarize(make_activity(commits=commits, prs=prs), [make_task("TS-1")]))["TS-1"]
    assert task["outcome"] == "review"
    assert task["evidence"] == "PR app#14 open"


def test_outcome_done_without_pr():
    card = make_task("TS-1", Status.DONE, changed="2026-10-29T12:00:00+00:00")
    summary = summarize(make_activity(), [card])
    task = entries(summary)["TS-1"]
    assert task["outcome"] == "done_without_pr"
    assert task["evidence"] == "status done since 2026-10-29"
    old = make_task("TS-2", Status.DONE, changed="2026-09-01T12:00:00+00:00")
    assert "TS-2" not in entries(summarize(make_activity(), [old]))


def test_outcome_in_progress():
    commits = [make_commit("TS-1", "2026-10-27"), make_commit("TS-1", "2026-10-28")]
    task = entries(summarize(make_activity(commits=commits), [make_task("TS-1")]))["TS-1"]
    assert task["outcome"] == "in_progress"
    assert task["evidence"] == "2 commits on 2 days"


def test_outcome_rules_are_ordered():
    prs = [
        make_pr(1, "TS-1", base="release"),
        make_pr(2, "TS-1", base="master", merged="2026-10-30T12:00:00Z"),
        make_pr(3, "TS-1", state="open", merged=None),
    ]
    commits = [make_commit("TS-1", "2026-10-27")]
    card = make_task("TS-1", Status.VALIDATION)
    task = entries(summarize(make_activity(commits=commits, prs=prs), [card]))["TS-1"]
    assert task["outcome"] == "production"
    assert "app#2" in task["evidence"]
    without_master = entries(summarize(make_activity(commits=commits, prs=prs[::2]), [card]))
    assert without_master["TS-1"]["outcome"] == "homologation"
    only_open = entries(summarize(make_activity(commits=commits, prs=prs[2:]), [make_task("TS-1")]))
    assert only_open["TS-1"]["outcome"] == "review"


def test_outcome_evidence_text():
    prs = [make_pr(21, "TS-1", repo="web", base="master", merged="2026-10-30T12:00:00Z")]
    task = entries(summarize(make_activity(prs=prs)))["TS-1"]
    assert task["evidence"] == "PR web#21 merged into master on 2026-10-30"


def test_top_cuts_per_theme_and_counts_more():
    commits = [make_commit(f"TS-{n}", "2026-10-27") for n in range(1, 6)]
    commits += [make_commit("TS-1", "2026-10-28")]
    tasks = [make_task(f"TS-{n}", epic="TS-100") for n in range(1, 6)]
    summary = summarize(make_activity(commits=commits), tasks, top=3)
    theme = summary["themes"][0]
    assert [task["key"] for task in theme["tasks"]] == ["TS-1", "TS-2", "TS-3"]
    assert theme["more"] == 2
    assert summary["totals"]["tasks"] == 5
    full = summarize(make_activity(commits=commits), tasks)
    assert full["themes"][0]["more"] == 0
    assert len(full["themes"][0]["tasks"]) == 5


def test_blockers_blocked_and_stuck():
    tasks = [
        make_task("TS-1", Status.BLOCKED),
        make_task("TS-2", Status.IN_PROGRESS, updated="2026-10-20T12:00:00+00:00"),
        make_task("TS-3", Status.IN_PROGRESS),
    ]
    summary = summarize(make_activity(), tasks)
    kinds = {blocker["key"]: blocker["kind"] for blocker in summary["blockers"]}
    assert kinds == {"TS-1": "blocked", "TS-2": "stuck"}
    stuck = next(blocker for blocker in summary["blockers"] if blocker["key"] == "TS-2")
    assert stuck["updated"] == "2026-10-20"
    assert stuck["url"].endswith("TS-2")


def test_keyless():
    commits = [make_commit(None, "2026-10-27", f"anotação {n}", repo="notes") for n in range(12)]
    commits.append(make_commit(None, "2026-10-27", "outro", repo="docs"))
    summary = summarize(make_activity(commits=commits))
    assert summary["keyless"]["commits"] == 13
    assert summary["keyless"]["repos"] == ["docs", "notes"]
    assert len(summary["keyless"]["subjects"]) == 10


def test_totals():
    commits = [
        make_commit("TS-1", "2026-10-27"),
        make_commit("TS-2", "2026-10-27"),
        make_commit(None, "2026-10-27", "sem chave"),
    ]
    prs = [make_pr(1, "TS-1"), make_pr(2, "TS-3", state="open", merged=None)]
    summary = summarize(make_activity(commits=commits, prs=prs))
    totals = summary["totals"]
    assert totals["tasks"] == 3
    assert totals["commits"] == 3
    assert totals["prs_merged"] == 1
    assert totals["outcomes"] == {
        "production": 1,
        "homologation": 0,
        "review": 1,
        "done_without_pr": 0,
        "in_progress": 1,
        "none": 0,
    }


def test_status_as_of_today():
    summary = summarize(make_activity(), [make_task("TS-1")])
    assert summary["status_as_of"] == "2026-11-03"
    assert summary["window"] == WINDOW
    assert summary["jira"] is True


def test_without_cards():
    commits = [make_commit("TS-1", "2026-10-27")]
    prs = [make_pr(3, "TS-1", base="release")]
    summary = summarize(make_activity(commits=commits, prs=prs, warnings=["gh: x"]))
    task = entries(summary)["TS-1"]
    assert summary["jira"] is False
    assert task["status"] is None and task["url"] is None
    assert task["title"] == "TS-1 entrega 3"
    assert task["outcome"] == "homologation"
    assert summary["blockers"] == []
    assert summary["warnings"] == ["gh: x"]


def test_a_daily_activity_is_refused():
    with pytest.raises(ValueError, match="ws standup report"):
        summarize(make_activity(window={"since": "2026-10-26", "until": "2026-10-27"}))
