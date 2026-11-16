import json
from datetime import UTC, date, datetime

from ws.cli import main
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


def test_in_progress_without_activity_and_old_update_is_stuck():
    old = datetime(2026, 10, 20, 9, 0, tzinfo=UTC)
    result = evaluate([make_task("TS-101", Status.IN_PROGRESS, old)], make_activity(), TODAY, 3)
    assert result["stuck"] == [
        {"key": "TS-101", "last_activity": None, "updated": "2026-10-20", "workdays": 3}
    ]


def test_in_progress_with_commit_in_window_is_not_stuck():
    old = datetime(2026, 10, 20, 9, 0, tzinfo=UTC)
    activity = make_activity(last_activity={"TS-101": "2026-10-26"})
    result = evaluate([make_task("TS-101", Status.IN_PROGRESS, old)], activity, TODAY, 3)
    assert result["stuck"] == []


def test_in_progress_updated_on_the_cutoff_day_is_not_stuck():
    cutoff = datetime(2026, 10, 22, 9, 0, tzinfo=UTC)
    result = evaluate([make_task("TS-101", Status.IN_PROGRESS, cutoff)], make_activity(), TODAY, 3)
    assert result["stuck"] == []


def test_moving_card_is_not_stuck():
    old = datetime(2026, 10, 20, 9, 0, tzinfo=UTC)
    task = make_task("TS-101", Status.IN_PROGRESS, old)
    result = evaluate([task], make_activity(), TODAY, 3, moving=frozenset({"TS-101"}))
    assert result == {"stuck": []}


def make_card(**overrides) -> dict:
    card = {
        "key": "TS-101",
        "title": "Titulo de exemplo",
        "status_name": "In Progress",
        "status_category": "indeterminate",
        "epic_key": None,
        "epic_title": None,
        "reporter_is_me": True,
        "updated": "2026-10-26T09:00:00+00:00",
    }
    card.update(overrides)
    return card


def run_status(tmp_path, cards, capsys, config_text, activity=None):
    from ws.config import config_dir

    (config_dir() / "config.toml").write_text(config_text, encoding="utf-8")
    cards_file = tmp_path / "cards.json"
    cards_file.write_text(json.dumps({"platform": "jira", "cards": cards}))
    activity_file = tmp_path / "activity.json"
    activity_file.write_text(json.dumps(activity or make_activity()))
    code = main(
        [
            "task",
            "status",
            "--cards",
            str(cards_file),
            "--activity",
            str(activity_file),
            "--today",
            "2026-10-27",
        ]
    )
    return code, capsys.readouterr()


JIRA_CONFIG = '[tracker]\nkind = "jira"\n[tracker.jira]\nsite = "https://example.atlassian.net"\nemail = "dev@example.com"\n'  # noqa: E501


def test_cli_maps_overrides_from_config(ws_config, tmp_path, capsys):
    config = JIRA_CONFIG + '[tracker.jira.status_overrides]\n"In Validation" = "validation"\n'
    card = make_card(status_name="In Validation")
    code, out = run_status(tmp_path, [card], capsys, config)
    assert code == 0
    payload = json.loads(out.out)
    assert payload["tasks"][0]["status"] == "validation"
    assert "suggestions" not in payload
    assert payload["stuck"] == []


def test_cli_malformed_card_exits_2(ws_config, tmp_path, capsys):
    card = make_card()
    del card["updated"]
    code, out = run_status(tmp_path, [card], capsys, JIRA_CONFIG)
    assert code == 2
    assert "updated" in out.err


def test_cli_without_config_exits_2(ws_config, tmp_path, capsys):
    cards_file = tmp_path / "cards.json"
    cards_file.write_text(json.dumps({"platform": "jira", "cards": []}))
    activity_file = tmp_path / "activity.json"
    activity_file.write_text(json.dumps(make_activity()))
    code = main(["task", "status", "--cards", str(cards_file), "--activity", str(activity_file)])
    assert code == 2
    assert "config.toml" in capsys.readouterr().err


def test_cli_stuck_uses_the_configured_window(ws_config, tmp_path, capsys):
    cards = [
        make_card(key="TS-101", updated="2026-10-19T09:00:00+00:00"),
        make_card(key="TS-103", updated="2026-10-21T09:00:00+00:00"),
        make_card(
            key="TS-102",
            status_name="To Do",
            status_category="new",
            updated="2026-10-26T09:00:00+00:00",
        ),
    ]
    commit = {
        "repo": "app",
        "sha": "abc123",
        "date": "2026-10-26",
        "subject": "x",
        "keys": ["TS-102"],
    }
    activity = make_activity(commits=[commit])
    config = JIRA_CONFIG + "[standup]\nstale_workdays = 5\n"
    code, out = run_status(tmp_path, cards, capsys, config, activity)
    assert code == 0
    payload = json.loads(out.out)
    assert payload["stuck"] == [
        {"key": "TS-101", "last_activity": None, "updated": "2026-10-19", "workdays": 5}
    ]
    assert "suggestions" not in payload


def test_review_without_activity_and_old_update_is_stuck():
    old = datetime(2026, 10, 20, 9, 0, tzinfo=UTC)
    result = evaluate([make_task("TS-101", Status.REVIEW, updated=old)], make_activity(), TODAY, 3)
    assert [item["key"] for item in result["stuck"]] == ["TS-101"]


def test_ready_deploy_and_blocked_are_never_stuck():
    old = datetime(2026, 10, 20, 9, 0, tzinfo=UTC)
    activity = make_activity(
        commits=[
            {
                "repo": "app",
                "sha": "abc123",
                "date": "2026-10-26",
                "subject": "x",
                "keys": ["TS-102"],
            }
        ]
    )
    tasks = [
        make_task("TS-101", Status.READY_DEPLOY, updated=old),
        make_task("TS-102", Status.BLOCKED, updated=old),
    ]
    assert evaluate(tasks, activity, TODAY, 3) == {"stuck": []}
