"""The time log: marks and session activity on cards, and the intervals they make.

`~/.local/share/workspace/timelog/<YYYY-MM>.jsonl` is private (0600 in a 0700 folder), append-only
and outside the repo; one JSON object per line. `ws time start|stop` write `start` and `stop`
events, the session hook writes `activity` events. This module reads them back into intervals;
`ws.timereport` turns the intervals into hours.
Design: docs/specs/2026-11-24-time-tracking-design.md.
"""

import json
import os
import re
from collections import defaultdict
from dataclasses import dataclass
from datetime import date, datetime, time, timedelta
from pathlib import Path

from ws.config import data_dir

VERSION = 1
EVENTS = ("start", "stop", "activity")
REF = re.compile(r"[A-Z][A-Z0-9_]*-[0-9]+")
CLOCK = re.compile(r"([01]?\d|2[0-3]):([0-5]\d)")
LOOKBACK = timedelta(days=31)
FOLDER_MODE = 0o700
FILE_MODE = 0o600


class TimeRefused(Exception):
    """A reason to stop, with the exit code it ends in."""

    def __init__(self, message: str, code: int = 1):
        super().__init__(message)
        self.code = code


@dataclass(frozen=True)
class Event:
    event: str
    card: str | None
    at: datetime
    source: str
    repo: str | None = None
    branch: str | None = None


@dataclass(frozen=True)
class Interval:
    card: str
    start: datetime
    end: datetime
    source: str

    @property
    def minutes(self) -> float:
        return (self.end - self.start).total_seconds() / 60


def _now() -> datetime:
    return datetime.now().astimezone().replace(microsecond=0)


def timelog_dir() -> Path:
    return data_dir() / "timelog"


def _month_name(day: date) -> str:
    return f"{day:%Y-%m}"


def append(record: dict, at: datetime) -> None:
    """One line in the month file of `at`, created 0600 in a 0700 folder."""
    folder = timelog_dir()
    folder.mkdir(mode=FOLDER_MODE, parents=True, exist_ok=True)
    folder.chmod(FOLDER_MODE)
    line = json.dumps({"v": VERSION, **record}, ensure_ascii=False) + "\n"
    path = folder / f"{_month_name(at.date())}.jsonl"
    descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_APPEND | os.O_NOFOLLOW, FILE_MODE)
    try:
        os.fchmod(descriptor, FILE_MODE)
        os.write(descriptor, line.encode("utf-8"))
    finally:
        os.close(descriptor)


def _months(since: date, until: date) -> list[str]:
    names = []
    current = since.replace(day=1)
    while current <= until:
        names.append(_month_name(current))
        current = (current + timedelta(days=32)).replace(day=1)
    return names


def _parse_at(text: object) -> datetime | None:
    if not isinstance(text, str):
        return None
    try:
        return datetime.fromisoformat(text).astimezone()
    except ValueError:
        return None


def _event(raw: object) -> Event | None:
    if not isinstance(raw, dict) or raw.get("v") != VERSION or raw.get("event") not in EVENTS:
        return None
    at = _parse_at(raw.get("at"))
    card = raw.get("card")
    if at is None or not (card is None or (isinstance(card, str) and REF.fullmatch(card))):
        return None
    if card is None and raw["event"] != "activity":
        return None
    texts = {name: raw.get(name) for name in ("source", "repo", "branch")}
    if not all(value is None or isinstance(value, str) for value in texts.values()):
        return None
    return Event(raw["event"], card, at, texts["source"] or "", texts["repo"], texts["branch"])


def read(since: date, until: date) -> tuple[list[Event], int]:
    """The events of the month files that can matter for the days `since` to `until` (a month
    back too, for an interval opened before `since`), by time; and how many lines were skipped
    for being unreadable or not of this format."""
    events: list[Event] = []
    skipped = 0
    for name in _months(since - LOOKBACK, until + timedelta(days=1)):
        path = timelog_dir() / f"{name}.jsonl"
        try:
            text = path.read_text(encoding="utf-8", errors="replace")
        except FileNotFoundError:
            continue
        for line in text.splitlines():
            if not line.strip():
                continue
            try:
                found = _event(json.loads(line))
            except ValueError:
                found = None
            if found is None:
                skipped += 1
            else:
                events.append(found)
    events.sort(key=lambda item: item.at)
    return events, skipped


def replay(events: list[Event]) -> tuple[list[Interval], dict[str, datetime]]:
    """The closed marked intervals, and the cards still open with the time they opened.

    A start of a card already open and a stop of a card not open change nothing."""
    opened: dict[str, datetime] = {}
    closed: list[Interval] = []
    for item in events:
        if item.card is None:
            continue
        if item.event == "start":
            opened.setdefault(item.card, item.at)
        elif item.event == "stop" and item.card in opened:
            begin = opened.pop(item.card)
            if item.at > begin:
                closed.append(Interval(item.card, begin, item.at, "marked"))
    return closed, opened


def marked_intervals(events: list[Event], now: datetime, warnings: list[str]) -> list[Interval]:
    """Marked intervals. One still open runs to `now` when it opened today; an older one ends at
    the card's last activity of the day it opened, and without any it is left out (a warning)."""
    intervals, opened = replay(events)
    for card, begin in sorted(opened.items()):
        if begin.date() == now.date():
            end = now
        else:
            seen = [
                item.at
                for item in events
                if item.event == "activity"
                and item.card == card
                and item.at >= begin
                and item.at.date() == begin.date()
            ]
            if not seen:
                warnings.append(
                    f"{card}: the interval opened on {begin.date().isoformat()} has no stop "
                    "and no activity that day; left out"
                )
                continue
            end = max(seen)
        if end > begin:
            intervals.append(Interval(card, begin, end, "marked"))
    return intervals


def hook_intervals(events: list[Event], idle_minutes: int) -> list[Interval]:
    """Activity of one card with gaps of at most `idle_minutes` makes one interval, from its
    first to its last event; a lone event is an interval of no length (the card was touched)."""
    by_card: dict[str, list[datetime]] = defaultdict(list)
    for item in events:
        if item.event == "activity" and item.card:
            by_card[item.card].append(item.at)
    gap = timedelta(minutes=idle_minutes)
    intervals = []
    for card, stamps in sorted(by_card.items()):
        begin = last = stamps[0]
        for stamp in stamps[1:]:
            if stamp - last > gap:
                intervals.append(Interval(card, begin, last, "hook"))
                begin = stamp
            last = stamp
        intervals.append(Interval(card, begin, last, "hook"))
    return intervals


def _merged(spans: list[tuple[datetime, datetime]]) -> list[tuple[datetime, datetime]]:
    out: list[tuple[datetime, datetime]] = []
    for begin, end in sorted(spans):
        if out and begin <= out[-1][1]:
            out[-1] = (out[-1][0], max(out[-1][1], end))
        else:
            out.append((begin, end))
    return out


def _uncovered(item: Interval, cover: list[tuple[datetime, datetime]]) -> list[Interval]:
    """The parts of `item` that no span of `cover` (merged, sorted) covers."""
    if item.start == item.end:
        covered = any(begin <= item.start <= end for begin, end in cover)
        return [] if covered else [item]
    pieces = []
    cursor = item.start
    for begin, end in cover:
        if end <= cursor or begin >= item.end:
            continue
        if begin > cursor:
            pieces.append(Interval(item.card, cursor, begin, item.source))
        cursor = max(cursor, end)
    if cursor < item.end:
        pieces.append(Interval(item.card, cursor, item.end, item.source))
    return pieces


def evidence(
    events: list[Event], idle_minutes: int, now: datetime, warnings: list[str]
) -> list[Interval]:
    """Marked intervals, plus the hook intervals where no marked interval (of any card) covers."""
    marked = marked_intervals(events, now, warnings)
    cover = _merged([(item.start, item.end) for item in marked])
    hooked = [
        piece for item in hook_intervals(events, idle_minutes) for piece in _uncovered(item, cover)
    ]
    return sorted([*marked, *hooked], key=lambda item: (item.start, item.end, item.card))


def day_bounds(day: date) -> tuple[datetime, datetime]:
    return (
        datetime.combine(day, time.min).astimezone(),
        datetime.combine(day + timedelta(days=1), time.min).astimezone(),
    )


def clip(item: Interval, day: date) -> Interval | None:
    """The part of an interval inside a local day; None when none of it is."""
    first, after = day_bounds(day)
    if item.start == item.end:
        return item if first <= item.start < after else None
    begin, end = max(item.start, first), min(item.end, after)
    return Interval(item.card, begin, end, item.source) if begin < end else None


def parse_clock(text: str, now: datetime) -> datetime:
    """`HH:MM` as today at that local time; never later than `now`."""
    found = CLOCK.fullmatch(text.strip())
    if not found:
        raise TimeRefused(f"--at must be HH:MM, got {text!r}")
    at = now.replace(hour=int(found.group(1)), minute=int(found.group(2)), second=0)
    if at > now:
        raise TimeRefused(f"--at {text} is in the future; time is only marked as it happened")
    return at


def _check_ref(ref: str) -> None:
    if not REF.fullmatch(ref):
        raise TimeRefused(f"{ref!r} is not a card ref like TS-123")


def _state(at: datetime) -> dict[str, datetime]:
    events, _ = read(at.date(), at.date())
    return replay(events)[1]


def start(ref: str, at_text: str | None = None) -> dict:
    """Open an interval for the card; a card already open is left as it is, with a note."""
    _check_ref(ref)
    now = _now()
    at = parse_clock(at_text, now) if at_text is not None else now
    opened = _state(at)
    if ref in opened:
        return {
            "version": VERSION,
            "action": "none",
            "card": ref,
            "since": opened[ref].isoformat(),
            "notes": [f"{ref} is already open since {opened[ref].isoformat()}"],
        }
    append({"event": "start", "card": ref, "at": at.isoformat(), "source": "manual"}, at)
    return {"version": VERSION, "action": "started", "card": ref, "at": at.isoformat()}


def stop(ref: str | None = None, at_text: str | None = None) -> dict:
    """Close the card's open interval, or every open one without a card. A stop before the
    start is refused and nothing is written."""
    if ref is not None:
        _check_ref(ref)
    now = _now()
    at = parse_clock(at_text, now) if at_text is not None else now
    opened = _state(at)
    notes = []
    if ref is None:
        targets = sorted(opened)
        if not targets:
            notes.append("no interval is open")
    elif ref in opened:
        targets = [ref]
    else:
        targets = []
        notes.append(f"{ref} is not open")
    for card in targets:
        if at < opened[card]:
            raise TimeRefused(
                f"{card}: --at {at.strftime('%H:%M')} is before its start "
                f"({opened[card].isoformat()})"
            )
    closed = []
    for card in targets:
        append({"event": "stop", "card": card, "at": at.isoformat(), "source": "manual"}, at)
        minutes = round((at - opened[card]).total_seconds() / 60)
        closed.append({"card": card, "start": opened[card].isoformat(), "minutes": minutes})
    return {
        "version": VERSION,
        "action": "stopped" if closed else "none",
        "at": at.isoformat(),
        "stopped": closed,
        "notes": notes,
    }


def status(idle_minutes: int) -> dict:
    """The open intervals and today's minutes per card from marks and hook activity (each card
    on its own: an overlap of two cards is split only by `ws time report`)."""
    now = _now()
    today = now.date()
    events, skipped = read(today, today)
    warnings: list[str] = []
    if skipped:
        warnings.append(f"{skipped} unreadable lines of the time log were skipped")
    opened = replay(events)[1]
    totals: dict[str, dict[str, float]] = {}
    for item in evidence(events, idle_minutes, now, warnings):
        part = clip(item, today)
        if part is not None:
            row = totals.setdefault(part.card, {"marked": 0.0, "hook": 0.0})
            row[part.source] += part.minutes
    return {
        "version": VERSION,
        "date": today.isoformat(),
        "open": [{"card": card, "since": opened[card].isoformat()} for card in sorted(opened)],
        "today": [
            {
                "card": card,
                "minutes": round(row["marked"]) + round(row["hook"]),
                "marked": round(row["marked"]),
                "hook": round(row["hook"]),
            }
            for card, row in sorted(totals.items())
        ],
        "warnings": warnings,
    }
