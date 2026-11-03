"""Agrupa o trabalho de um período por tema (épico): o que foi entregue, o que está em revisão."""

from datetime import date, datetime

from ws.taskmodel import Status, Task
from ws.taskstatus import evaluate

SUBJECT_LIMIT = 5
KEYLESS_SUBJECT_LIMIT = 10
DEFAULT_BRANCHES = ("master", "main")
OUTCOMES = ("production", "homologation", "review", "done_without_pr", "in_progress")
NO_EPIC = "Sem épico"


def _local_day(stamp: str | None) -> date | None:
    # Local time, like the collector's window: a PR merged at 23:00 belongs to that local day.
    return None if stamp is None else datetime.fromisoformat(stamp).astimezone().date()


def _in_window(day: date | None, since: date, until: date) -> bool:
    return day is not None and since <= day <= until


def _pr_view(pr: dict) -> dict:
    merged = _local_day(pr["merged_at"])
    return {
        "ref": f"{pr['repo']}#{pr['number']}",
        "state": pr["state"],
        "base": pr["base"],
        "merged": merged.isoformat() if merged else None,
        "title": pr["title"],
    }


def _merged_in_window(prs: list[dict], since: date, until: date) -> list[dict]:
    return [pr for pr in prs if _in_window(_local_day(pr["merged_at"]), since, until)]


def _ref(pr: dict) -> str:
    return f"PR {pr['repo']}#{pr['number']}"


def _merged_text(pr: dict) -> str:
    return f"{_ref(pr)} merged into {pr['base']} on {_local_day(pr['merged_at'])}"


def _outcome(
    prs: list[dict], card: Task | None, commits: list[dict], since: date, until: date
) -> tuple[str | None, str | None]:
    merged = _merged_in_window(prs, since, until)
    for pr in merged:
        if pr["base"] in DEFAULT_BRANCHES:
            return "production", _merged_text(pr)
    if merged:
        return "homologation", _merged_text(merged[0])
    if card is not None and card.status in (Status.VALIDATION, Status.READY_DEPLOY):
        return "homologation", f"current status is {card.status.value}"
    for pr in prs:
        if pr["state"] == "open":
            return "review", f"{_ref(pr)} open"
    if card is not None and card.status is Status.DONE and not prs:
        changed = card.status_changed.astimezone().date() if card.status_changed else None
        if _in_window(changed, since, until):
            return "done_without_pr", f"status done since {changed}"
    if commits:
        days = len({commit["date"] for commit in commits})
        return "in_progress", f"{len(commits)} commits on {days} days"
    return None, None


def _task_entry(
    key: str, commits: list[dict], prs: list[dict], card: Task | None, since: date, until: date
) -> dict:
    ordered = sorted(commits, key=lambda commit: commit["date"], reverse=True)
    days = sorted({commit["date"] for commit in commits})
    outcome, evidence = _outcome(prs, card, commits, since, until)
    title = card.title if card else next((pr["title"] for pr in prs), None)
    return {
        "key": key,
        "title": title,
        "status": card.status.value if card else None,
        "url": card.url if card else None,
        "commits": len(commits),
        "active_days": len(days),
        "first_day": days[0] if days else None,
        "last_day": days[-1] if days else None,
        "subjects": [commit["subject"] for commit in ordered[:SUBJECT_LIMIT]],
        "prs": [_pr_view(pr) for pr in prs],
        "outcome": outcome,
        "evidence": evidence,
    }


def _blockers(tasks: list[Task] | None, activity: dict, today: date, stale: int) -> list[dict]:
    if tasks is None:
        return []
    cards = {task.key: task for task in tasks}
    blocked = [
        {
            "key": task.key,
            "title": task.title,
            "url": task.url,
            "updated": task.updated.date().isoformat(),
            "workdays": None,
            "kind": "blocked",
        }
        for task in cards.values()
        if task.status is Status.BLOCKED
    ]
    stuck = [
        {
            "key": item["key"],
            "title": cards[item["key"]].title,
            "url": cards[item["key"]].url,
            "updated": item["updated"],
            "workdays": item["workdays"],
            "kind": "stuck",
        }
        for item in evaluate(list(cards.values()), activity, today, stale)["stuck"]
    ]
    return [*blocked, *stuck]


def _theme_key(card: Task | None) -> tuple[str | None, str]:
    if card is not None and card.epic_key:
        return card.epic_key, card.epic_title or card.epic_key
    return None, NO_EPIC


def build_summary(
    activity: dict,
    tasks: list[Task] | None,
    today: date,
    stale_workdays: int,
    top: int | None = None,
) -> dict:
    window = activity["window"]
    if window.get("kind") != "period":
        raise ValueError("this activity is not a period: use ws standup report")
    since = date.fromisoformat(window["since"])
    until = date.fromisoformat(window["until"])
    cards = {task.key: task for task in tasks or []}

    commits_of: dict[str, list[dict]] = {}
    prs_of: dict[str, list[dict]] = {}
    for commit in activity["commits"]:
        for key in commit["keys"]:
            commits_of.setdefault(key, []).append(commit)
    for pr in activity["prs"]:
        for key in pr["keys"]:
            prs_of.setdefault(key, []).append(pr)
    for key, card in cards.items():
        if card.status is Status.DONE and _in_window(
            card.status_changed.astimezone().date() if card.status_changed else None, since, until
        ):
            commits_of.setdefault(key, [])

    found = [
        _task_entry(key, commits_of.get(key, []), prs_of.get(key, []), cards.get(key), since, until)
        for key in dict.fromkeys([*commits_of, *prs_of])
    ]

    themes: dict[tuple[str | None, str], list[dict]] = {}
    for entry in found:
        themes.setdefault(_theme_key(cards.get(entry["key"])), []).append(entry)

    def weight(entry: dict) -> int:
        return entry["commits"] + len(entry["prs"])

    ordered = []
    for (key, title), group in themes.items():
        group.sort(key=lambda e: (-weight(e), _neg_day(e["last_day"]), e["key"]))
        ordered.append((sum(weight(e) for e in group), key, title, group))
    ordered.sort(key=lambda item: (-item[0], item[2]))

    result_themes = []
    for _, key, title, group in ordered:
        shown = group if top is None else group[:top]
        result_themes.append(
            {"key": key, "title": title, "tasks": shown, "more": len(group) - len(shown)}
        )

    keyless = [commit for commit in activity["commits"] if not commit["keys"]]
    merged = {(pr["repo"], pr["number"]) for pr in _merged_in_window(activity["prs"], since, until)}
    counts = {name: 0 for name in (*OUTCOMES, "none")}
    for entry in found:
        counts[entry["outcome"] or "none"] += 1
    return {
        "window": window,
        "jira": tasks is not None,
        "status_as_of": today.isoformat(),
        "themes": result_themes,
        "blockers": _blockers(tasks, activity, today, stale_workdays),
        "keyless": {
            "commits": len(keyless),
            "repos": sorted({commit["repo"] for commit in keyless}),
            "subjects": [commit["subject"] for commit in keyless[:KEYLESS_SUBJECT_LIMIT]],
        },
        "totals": {
            "tasks": len(found),
            "commits": len(activity["commits"]),
            "prs_merged": len(merged),
            "outcomes": counts,
        },
        "warnings": activity["warnings"],
    }


def _neg_day(day: str | None) -> int:
    return -date.fromisoformat(day).toordinal() if day else 0
