"""Agrupa a atividade coletada por tarefa: ontem, hoje, bloqueios e o que não tem chave."""

from datetime import date

from ws.standup import keys_in
from ws.taskmodel import Status, Task
from ws.taskstatus import evaluate

SUBJECT_LIMIT = 5


def _yesterday(activity: dict, cards: dict[str, Task]) -> list[dict]:
    since = activity["window"]["since"]
    found: dict[str, dict] = {}

    def entry(key: str) -> dict:
        return found.setdefault(key, {"commits": [], "prs": [], "latest": ""})

    for commit in activity["commits"]:
        for key in commit["keys"]:
            item = entry(key)
            item["commits"].append(commit)
            item["latest"] = max(item["latest"], commit["date"])
    for pr in activity["prs"]:
        if pr["updated_at"][:10] < since:
            continue
        for key in pr["keys"]:
            item = entry(key)
            item["prs"].append(pr)
            item["latest"] = max(item["latest"], pr["updated_at"])

    result = []
    for key, item in sorted(found.items(), key=lambda pair: pair[1]["latest"], reverse=True):
        card = cards.get(key)
        title = None
        if card is not None:
            title = card.title
        else:
            title = next((pr["title"] for pr in activity["prs"] if key in pr["keys"]), None)
        commits = sorted(item["commits"], key=lambda commit: commit["date"], reverse=True)
        result.append(
            {
                "key": key,
                "title": title,
                "status": card.status.value if card else None,
                "url": card.url if card else None,
                "commits": len(commits),
                "subjects": [commit["subject"] for commit in commits[:SUBJECT_LIMIT]],
                "prs": [
                    {
                        "ref": f"{pr['repo']}#{pr['number']}",
                        "state": pr["state"],
                        "title": pr["title"],
                    }
                    for pr in item["prs"]
                ],
                "suggestion": None,
            }
        )
    return result


def _suggestion(found: dict) -> dict:
    return {name: found[name] for name in ("from", "to", "rule", "evidence")}


def build_report(
    activity: dict, tasks: list[Task] | None, today: date, stale_workdays: int
) -> dict:
    cards = {task.key: task for task in tasks or []}
    yesterday = _yesterday(activity, cards)
    evaluated = (
        evaluate(tasks, activity, today, stale_workdays)
        if tasks is not None
        else {"suggestions": [], "stuck": []}
    )
    blockers = [
        {
            "key": stuck["key"],
            "title": cards[stuck["key"]].title,
            "url": cards[stuck["key"]].url,
            "updated": stuck["updated"],
            "workdays": stuck["workdays"],
        }
        for stuck in evaluated["stuck"]
    ]
    blocked = {blocker["key"] for blocker in blockers}

    step_of: dict[str, str] = {}
    for step in activity["next_steps"]:
        for key in keys_in(step["text"]):
            step_of.setdefault(key, step["text"])

    suggestions = {item["key"]: _suggestion(item) for item in evaluated["suggestions"]}
    in_yesterday = {item["key"]: item for item in yesterday}
    for key, item in in_yesterday.items():
        item["suggestion"] = suggestions.get(key)

    today_entries = []
    for task in tasks or []:
        if task.key in blocked:
            continue
        wanted = (
            task.status is Status.IN_PROGRESS
            or task.key in step_of
            or (task.key in suggestions and task.key not in in_yesterday)
        )
        if not wanted:
            continue
        today_entries.append(
            {
                "key": task.key,
                "title": task.title,
                "status": task.status.value,
                "url": task.url,
                "next_step": step_of.get(task.key),
                "suggestion": None if task.key in in_yesterday else suggestions.get(task.key),
            }
        )
    shown = {entry["key"] for entry in today_entries}

    keyless = [commit for commit in activity["commits"] if not commit["keys"]]
    return {
        "window": activity["window"],
        "jira": tasks is not None,
        "yesterday": yesterday,
        "today": today_entries,
        "next_steps": [
            step for step in activity["next_steps"] if not shown & set(keys_in(step["text"]))
        ],
        "blockers": blockers,
        "keyless": {
            "commits": len(keyless),
            "repos": sorted({commit["repo"] for commit in keyless}),
        },
        "warnings": activity["warnings"],
    }
