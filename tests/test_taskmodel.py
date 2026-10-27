from datetime import UTC, datetime

from ws.taskmodel import Status, Task, task_to_json


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
