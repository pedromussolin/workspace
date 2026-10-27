"""Regras que sugerem mudança de status a partir da atividade coletada."""

from datetime import date

from ws.taskmodel import Status, Task
from ws.workdays import workdays_before


def _suggestion(task: Task, to: Status, rule: str, evidence: str) -> dict:
    return {
        "key": task.key,
        "from": task.status.value,
        "to": to.value,
        "rule": rule,
        "evidence": evidence,
    }


def _first_evidence(key: str, activity: dict) -> str | None:
    for commit in activity["commits"]:
        if key in commit["keys"]:
            return commit["sha"]
    for branch in activity["branches"]:
        if key in branch["keys"]:
            return branch["name"]
    return None


def _merged_pr_evidence(key: str, activity: dict) -> str | None:
    for pr in activity["prs"]:
        if pr["merged_at"] is not None and key in pr["keys"]:
            return f"{pr['repo']}#{pr['number']}"
    return None


def evaluate(tasks: list[Task], activity: dict, today: date, stale_workdays: int) -> dict:
    cutoff = workdays_before(today, stale_workdays)
    suggestions = []
    stuck = []
    for task in tasks:
        if task.status is Status.TODO:
            evidence = _first_evidence(task.key, activity)
            if evidence is not None:
                suggestions.append(_suggestion(task, Status.IN_PROGRESS, "R1", evidence))
        elif task.status is Status.IN_PROGRESS:
            evidence = _merged_pr_evidence(task.key, activity)
            if evidence is not None:
                suggestions.append(_suggestion(task, Status.VALIDATION, "R2", evidence))
                continue
            last = activity["last_activity"].get(task.key)
            if last is None and task.updated.date() < cutoff:
                stuck.append({"key": task.key, "last_activity": last})
    return {"suggestions": suggestions, "stuck": stuck}
