"""Business days, windows and status of an observation plan (pure: no files, no tools)."""

from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo

from ws.workdays import business_days, is_business_day, next_business_day, previous_business_day

DEFAULT_TIMEZONE = "America/Sao_Paulo"
DEFAULT_DAYS = 5


def _date(value: date | str) -> date:
    return value if isinstance(value, date) else date.fromisoformat(value)


def _short(value: date | str) -> str:
    return _date(value).strftime("%d/%m")


def due_day(today: date, extra: frozenset[date]) -> date:
    return previous_business_day(today, extra)


def day_number(day: date, switched_off: date, extra: frozenset[date]) -> int:
    if day <= switched_off:
        return 0
    return len(business_days(switched_off, day, extra))


def day_window(
    day: date, switched_off: date, timezone: str, extra: frozenset[date]
) -> tuple[datetime, datetime]:
    zone = ZoneInfo(timezone)
    first = max(previous_business_day(day, extra), switched_off) + timedelta(days=1)
    last = day + timedelta(days=1)
    return (
        datetime(first.year, first.month, first.day, tzinfo=zone),
        datetime(last.year, last.month, last.day, tzinfo=zone),
    )


def day_problem(day: date, switched_off: date, today: date, extra: frozenset[date]) -> str | None:
    if not is_business_day(day, extra):
        following = next_business_day(day, extra)
        return f"{day} is not a business day; the next one is {following}"
    if day <= switched_off:
        first = next_business_day(switched_off, extra)
        return f"{day} is not after the switch-off day {switched_off}; day 1 is {first}"
    due = due_day(today, extra)
    if day > due:
        closes = day + timedelta(days=1)
        return f"the window of {day} closes at 00:00 of {closes}; the latest closed day is {due}"
    return None


def _day_state(day: date, checks: list[str], current: dict) -> str:
    verdicts = [current.get((day.isoformat(), check)) for check in checks]
    if any(verdict == "fail" for verdict in verdicts):
        return "fail"
    if any(verdict is None for verdict in verdicts):
        return "incomplete"
    return "ok"


def plan_status(
    plan: dict,
    project: str,
    hashes: dict[str, str],
    rows: list[dict],
    today: date,
    extra: frozenset[date],
) -> dict:
    switched_off = _date(plan["switched_off"])
    total = plan.get("days", DEFAULT_DAYS)
    checks = [check["id"] for check in plan.get("checks", [])]
    due = due_day(today, extra)
    number = day_number(due, switched_off, extra)
    first = next_business_day(switched_off, extra)

    latest = {(item["day"], item["check"]): item for item in rows if item["check"] in checks}
    current = {
        key: item["verdict"] for key, item in latest.items() if item["hash"] == hashes.get(key[1])
    }
    stale = sorted(key for key in latest if key not in current)

    days = business_days(switched_off, due, extra)
    states = {day: _day_state(day, checks, current) for day in days}
    attention = [day.isoformat() for day in days if states[day] == "fail"]
    missing = [day.isoformat() for day in days if states[day] == "incomplete" and day != due]
    pending = [check for check in checks if (due.isoformat(), check) not in current] if days else []

    streak = 0
    start = None
    if days:
        start = days[-1]
        if states[start] == "incomplete":
            start = days[-2] if len(days) > 1 else None
    if start is not None:
        for day in reversed(days[: days.index(start) + 1]):
            if states[day] != "ok":
                break
            streak += 1

    if number == 0:
        state = "waiting"
    elif streak >= total:
        state = "done"
    elif start is not None and states[start] == "fail":
        state = "attention"
    else:
        state = "observing"

    return {
        "task": plan["task"],
        "project": project,
        "job": plan.get("job", ""),
        "days": total,
        "due_day": due.isoformat(),
        "first_day": first.isoformat(),
        "day": number,
        "pending": pending,
        "missing_days": missing,
        "stale": [{"day": day, "check": check} for day, check in stale],
        "attention_days": attention,
        "streak": streak,
        "state": state,
    }


def status_document(entries: list[dict], today: date, problems: list[str]) -> dict:
    return {"version": 1, "today": today.isoformat(), "plans": entries, "problems": problems}


def _gaps(entry: dict) -> str:
    """Past days without a full set of values and values recorded before a check changed: both
    keep the streak from growing until `run --day` fills them."""
    text = ""
    missing = entry.get("missing_days", [])
    if missing:
        text += f"; {'falta' if len(missing) == 1 else 'faltam'} "
        text += ", ".join(_short(day) for day in missing)
    stale = len(entry.get("stale", []))
    if stale:
        text += f"; {stale} {'desatualizado' if stale == 1 else 'desatualizados'}"
    return text


def status_line(entry: dict) -> str:
    head = entry["task"]
    if entry.get("job"):
        head += f" ({entry['job']})"
    state = entry["state"]
    if state == "waiting":
        return f"{head}: aguardando o dia 1 ({_short(entry['first_day'])})"
    progress = f"dia {entry['day']} de {entry['days']}"
    if state == "done":
        return f"{head}: {progress}, pode desligar de vez"
    if state == "attention":
        dates = ", ".join(_short(day) for day in entry["attention_days"])
        return f"{head}: {progress}, atenção em {dates}{_gaps(entry)}"
    text = f"{head}: {progress}"
    if entry["pending"]:
        text += f", pendente: {', '.join(entry['pending'])}"
    text += _gaps(entry)
    streak = entry["streak"]
    if streak:
        text += f"; {streak} {'dia seguido' if streak == 1 else 'dias seguidos'} ok"
    return text
