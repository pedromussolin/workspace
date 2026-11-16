"""PT-BR Markdown report of an observation, the execution evidence of a change record.

Prints ids, labels, hashes, values and times; never the text of a query.
"""

from datetime import date, datetime
from zoneinfo import ZoneInfo

from ws.observestatus import DEFAULT_TIMEZONE, day_window
from ws.workdays import business_days


def _short(day: date) -> str:
    return day.strftime("%d/%m")


def _offset(moment: datetime) -> str:
    raw = moment.strftime("%z")
    return f"{raw[:3]}:{raw[3:]}"


def _times(row: dict, zone: ZoneInfo) -> str:
    if not row.get("started") or not row.get("finished"):
        return ""
    started = datetime.fromisoformat(row["started"]).astimezone(zone)
    if row.get("times") == "record":
        # A value typed by a person has one moment: when it was recorded.
        return f"registrado às {started:%H:%M:%S} ({_offset(started)})"
    finished = datetime.fromisoformat(row["finished"]).astimezone(zone)
    return f"{started:%H:%M:%S}–{finished:%H:%M:%S} ({_offset(started)})"


def _number(value: object) -> str:
    if isinstance(value, float) and value.is_integer():
        return str(int(value))
    return str(value)


def _cell(row: dict | None, hashes: dict[str, str], zone: ZoneInfo) -> str:
    if row is None:
        return "—"
    if row.get("kind") == "manual" or isinstance(row.get("value"), bool):
        parts = ["sim" if row.get("value") else "não"]
        if row.get("by"):
            parts.append(f"por {row['by']}")
    else:
        parts = [_number(row.get("value")), "ok" if row.get("verdict") == "pass" else "falhou"]
    when = _times(row, zone)
    if when:
        parts.append(when)
    text = " · ".join(parts)
    if row.get("hash") != hashes.get(row["check"]):
        text += " (desatualizado)"
    return _escape(text)


def _escape(text: str) -> str:
    return text.replace("|", "\\|")


def _verdict(entry: dict) -> str:
    state = entry["state"]
    if state == "done":
        return f"pode desligar de vez: {entry['streak']} dias úteis seguidos ok"
    if state == "attention":
        dates = ", ".join(_short(date.fromisoformat(day)) for day in entry["attention_days"])
        return f"atenção em {dates}; sequência atual {entry['streak']} de {entry['days']}"
    if state == "waiting":
        return f"aguardando o dia 1 ({_short(date.fromisoformat(entry['first_day']))})"
    return f"em observação: dia {entry['day']} de {entry['days']}"


def render(
    plan: dict,
    hashes: dict[str, str],
    rows: list[dict],
    entry: dict,
    title: str | None,
    extra: frozenset[date] = frozenset(),
) -> str:
    switched_off = date.fromisoformat(str(plan["switched_off"]))
    timezone = plan.get("timezone", DEFAULT_TIMEZONE)
    zone = ZoneInfo(timezone)
    checks = plan.get("checks", [])
    latest = {(item["day"], item["check"]): item for item in rows}
    due = date.fromisoformat(entry["due_day"])
    days = business_days(switched_off, due, extra)
    closed = ""
    if plan.get("closed"):
        closed = f"; observação encerrada em {date.fromisoformat(plan['closed']):%d/%m/%Y}"

    lines = [
        f"# Observação {plan['task']}: {title or plan.get('job', '')}",
        "",
        f"Desligado em {switched_off:%d/%m/%Y}; {entry['days']} dias úteis de observação; "
        f"fuso {timezone}{closed}.",
        "",
        "| Dia | Janela | " + " | ".join(_escape(c.get("label") or c["id"]) for c in checks) + " |",
        "|---|---|" + "---|" * len(checks),
    ]
    for number, day in enumerate(days, start=1):
        start, end = day_window(day, switched_off, timezone, extra)
        window = f"{start:%d/%m %H:%M} – {end:%d/%m %H:%M}"
        cells = [_cell(latest.get((day.isoformat(), c["id"])), hashes, zone) for c in checks]
        lines.append(f"| {number} · {_short(day)} | {window} | " + " | ".join(cells) + " |")
    consultas = ", ".join(f"{c['id']} {hashes.get(c['id'], '—')}" for c in checks)
    lines += ["", f"Consultas: {consultas}", "", f"**Resultado:** {_verdict(entry)}", ""]
    return "\n".join(lines)
