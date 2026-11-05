"""Modelo neutro de tarefa: não conhece o tracker de origem, só o formato comum."""

from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum


class Status(StrEnum):
    TODO = "todo"
    IN_PROGRESS = "in_progress"
    REVIEW = "review"
    VALIDATION = "validation"
    READY_DEPLOY = "ready_deploy"
    BLOCKED = "blocked"
    DONE = "done"
    CANCELLED = "cancelled"


RUNG: dict[Status, int] = {
    Status.TODO: 0,
    Status.IN_PROGRESS: 1,
    Status.REVIEW: 1,
    Status.VALIDATION: 2,
    Status.READY_DEPLOY: 3,
    Status.DONE: 4,
}
STATUS_AT_RUNG: dict[int, Status] = {
    1: Status.IN_PROGRESS,
    2: Status.VALIDATION,
    3: Status.READY_DEPLOY,
    4: Status.DONE,
}


@dataclass(frozen=True)
class Task:
    ref: str
    key: str
    title: str
    url: str
    status: Status
    epic_key: str | None
    epic_title: str | None
    requested_by_other: bool
    updated: datetime
    is_epic: bool = False


def task_to_json(task: Task) -> dict:
    return {
        "ref": task.ref,
        "key": task.key,
        "title": task.title,
        "url": task.url,
        "status": task.status.value,
        "epic_key": task.epic_key,
        "epic_title": task.epic_title,
        "requested_by_other": task.requested_by_other,
        "updated": task.updated.isoformat(),
        "is_epic": task.is_epic,
    }
