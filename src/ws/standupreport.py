"""Agrupa a atividade coletada por tarefa: ontem, hoje, bloqueios e o que não tem chave."""

from datetime import date, datetime, time

from ws.standup import keys_in
from ws.taskmodel import Status, Task
from ws.taskstatus import ACTIVE_STATUSES, evaluate

SUBJECT_LIMIT = 5
TODAY_STATUSES = (*ACTIVE_STATUSES, Status.READY_DEPLOY)


def _yesterday(activity: dict, cards: dict[str, Task]) -> list[dict]:
    # Local midnight, like the collector's `git log --since`; PR timestamps carry their own offset.
    since = datetime.combine(date.fromisoformat(activity["window"]["since"]), time.min).astimezone()
    found: dict[str, dict] = {}

    def entry(key: str) -> dict:
        return found.setdefault(key, {"commits": [], "prs": [], "latest": date.min})

    for commit in activity["commits"]:
        for key in commit["keys"]:
            item = entry(key)
            item["commits"].append(commit)
            item["latest"] = max(item["latest"], date.fromisoformat(commit["date"]))
    for pr in activity["prs"]:
        updated = datetime.fromisoformat(pr["updated_at"]).astimezone()
        if updated < since:
            continue
        for key in pr["keys"]:
            item = entry(key)
            item["prs"].append(pr)
            item["latest"] = max(item["latest"], updated.date())

    result = []
    for key, item in sorted(found.items(), key=lambda pair: pair[1]["latest"], reverse=True):
        card = cards.get(key)
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


def _suggestion(move: dict) -> dict:
    return {
        "from": move["from"],
        "to": move["to"],
        "rule": "board",
        "evidence": move["environment"] or "commit",
    }


def build_report(
    activity: dict,
    tasks: list[Task] | None,
    today: date,
    stale_workdays: int,
    top: int | None = None,
    board: dict | None = None,
) -> dict:
    if activity["window"].get("kind") == "period":
        raise ValueError("this activity is a period: use ws standup summary")
    cards = {task.key: task for task in tasks or []}
    yesterday = _yesterday(activity, cards)
    moving = frozenset(move["key"] for move in board["moves"]) if board is not None else frozenset()
    evaluated = (
        evaluate(tasks, activity, today, stale_workdays, moving)
        if tasks is not None
        else {"stuck": []}
    )
    blocked_cards = [
        {
            "key": task.key,
            "title": task.title,
            "url": task.url,
            "updated": task.updated.date().isoformat(),
            "workdays": None,
            "kind": "blocked",
        }
        for task in {task.key: task for task in tasks or []}.values()
        if task.status is Status.BLOCKED
    ]
    stuck_cards = [
        {
            "key": stuck["key"],
            "title": cards[stuck["key"]].title,
            "url": cards[stuck["key"]].url,
            "updated": stuck["updated"],
            "workdays": stuck["workdays"],
            "kind": "stuck",
        }
        for stuck in evaluated["stuck"]
    ]
    blockers = [*blocked_cards, *stuck_cards]
    blocked = {blocker["key"] for blocker in blockers}

    step_of: dict[str, str] = {}
    for step in activity["next_steps"]:
        for key in keys_in(step["text"]):
            step_of.setdefault(key, step["text"])

    suggestions = {
        move["key"]: _suggestion(move) for move in (board["moves"] if board is not None else [])
    }
    in_yesterday = {item["key"]: item for item in yesterday}
    for key, item in in_yesterday.items():
        item["suggestion"] = suggestions.get(key)

    today_entries = []
    listed: set[str] = set()
    for task in tasks or []:
        if task.key in listed:
            continue
        if task.key in blocked and task.key not in suggestions:
            continue
        wanted = (
            task.status in TODAY_STATUSES
            or task.key in step_of
            or (task.key in suggestions and task.key not in in_yesterday)
        )
        if not wanted:
            continue
        listed.add(task.key)
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

    moves = [
        {"key": move["key"], "from": move["from"], "to": move["to"]}
        for move in (board["moves"] if board is not None else [])
    ]
    more = {"yesterday": 0, "today": 0}
    if top is not None:
        more = {
            "yesterday": max(len(yesterday) - top, 0),
            "today": max(len(today_entries) - top, 0),
        }
        yesterday = yesterday[:top]
        today_entries = today_entries[:top]

    keyless = [commit for commit in activity["commits"] if not commit["keys"]]
    return {
        "window": activity["window"],
        "tracker": tasks is not None,
        "yesterday": yesterday,
        "today": today_entries,
        "next_steps": [
            step for step in activity["next_steps"] if not shown & set(keys_in(step["text"]))
        ],
        "blockers": blockers,
        "more": more,
        "moves": moves,
        "to_confirm": board["to_confirm"] if board is not None else [],
        "keyless": {
            "commits": len(keyless),
            "repos": sorted({commit["repo"] for commit in keyless}),
        },
        "warnings": [*activity["warnings"], *(board["warnings"] if board is not None else [])],
    }
