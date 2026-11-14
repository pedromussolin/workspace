"""Detecta cards parados: em andamento ou em revisão, sem atividade e sem mexida no Jira."""

from datetime import date

from ws.taskmodel import Status, Task
from ws.workdays import workdays_before

ACTIVE_STATUSES = (Status.IN_PROGRESS, Status.REVIEW)


def evaluate(
    tasks: list[Task],
    activity: dict,
    today: date,
    stale_workdays: int,
    moving: frozenset[str] = frozenset(),
) -> dict:
    cutoff = workdays_before(today, stale_workdays)
    stuck = []
    for task in tasks:
        if task.status not in ACTIVE_STATUSES or task.key in moving:
            continue
        if activity["last_activity"].get(task.key) is None and task.updated.date() < cutoff:
            stuck.append(
                {
                    "key": task.key,
                    "last_activity": None,
                    "updated": task.updated.date().isoformat(),
                    "workdays": stale_workdays,
                }
            )
    return {"stuck": stuck}
