from dataclasses import replace
from datetime import UTC, datetime

from ws.taskmodel import RUNG, STATUS_AT_RUNG, Status, Task, task_to_json


def test_task_to_json_uses_plain_values():
    task = Task(
        "jira:TS-101",
        "TS-101",
        "[FRONT] Tela",
        "https://example.atlassian.net/browse/TS-101",
        Status.IN_PROGRESS,
        "TS-100",
        "[FRONT] Épico",
        False,
        datetime(2026, 10, 26, 9, 0, tzinfo=UTC),
    )
    data = task_to_json(task)
    assert data["status"] == "in_progress"
    assert data["updated"] == "2026-10-26T09:00:00+00:00"


def test_task_to_json_has_is_epic():
    task = Task(
        "jira:TS-100",
        "TS-100",
        "[FRONT] Épico",
        "https://example.atlassian.net/browse/TS-100",
        Status.IN_PROGRESS,
        None,
        None,
        False,
        datetime(2026, 10, 26, 9, 0, tzinfo=UTC),
        is_epic=True,
    )
    assert task_to_json(task)["is_epic"] is True
    assert task_to_json(replace(task, is_epic=False))["is_epic"] is False


def test_status_has_the_workflow_stage_values():
    assert Status("review") is Status.REVIEW
    assert Status("ready_deploy") is Status.READY_DEPLOY
    assert Status("blocked") is Status.BLOCKED


def test_rungs_order_the_card_stages():
    assert [RUNG[status] for status in (Status.TODO, Status.IN_PROGRESS, Status.REVIEW)] == [
        0,
        1,
        1,
    ]
    assert RUNG[Status.VALIDATION] == 2
    assert RUNG[Status.READY_DEPLOY] == 3
    assert RUNG[Status.DONE] == 4
    assert Status.BLOCKED not in RUNG
    assert Status.CANCELLED not in RUNG


def test_status_at_rung_names_the_status_a_rung_proves():
    assert STATUS_AT_RUNG == {
        1: Status.IN_PROGRESS,
        2: Status.VALIDATION,
        3: Status.READY_DEPLOY,
        4: Status.DONE,
    }
