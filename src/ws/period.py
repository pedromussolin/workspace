"""Parser de períodos em português para o standup: texto livre vira uma janela de datas."""

import re
import unicodedata
from calendar import monthrange
from dataclasses import dataclass
from datetime import date, timedelta

from ws.workdays import WEEKEND_DAYS, workdays_before

MAX_DAYS = 120
LEADING = ("de", "da", "do", "na", "no", "em", "nos", "nas", "os")
MONTHS = (
    "janeiro",
    "fevereiro",
    "marco",
    "abril",
    "maio",
    "junho",
    "julho",
    "agosto",
    "setembro",
    "outubro",
    "novembro",
    "dezembro",
)
MONTH_LABELS = (
    "janeiro",
    "fevereiro",
    "março",
    "abril",
    "maio",
    "junho",
    "julho",
    "agosto",
    "setembro",
    "outubro",
    "novembro",
    "dezembro",
)
MONTH_ABBREVIATIONS = tuple(name[:3] for name in MONTHS)
ACCEPTED_FORMS = (
    "hoje; ontem; esta semana; semana passada; últimos N dias; últimos N dias úteis; "
    "este mês; mês passado; outubro, out, outubro de 2026, 10/2026; "
    "20/10 a 31/10 (also 'de 20/10 até 31/10', 20/10/2026 a 31/10/2026, "
    "2026-10-20..2026-10-31); 20/10; desde 20/10"
)

DAY = r"(?:\d{4}-\d{2}-\d{2}|\d{1,2}/\d{1,2}(?:/\d{4})?)"
RANGE = re.compile(rf"({DAY})\s*(?:\.\.|a|ate)\s*({DAY})")
SINCE_DAY = re.compile(rf"desde\s+({DAY})")
ONE_DAY = re.compile(rf"({DAY})")
MONTH_YEAR = re.compile(r"(\d{1,2})/(\d{4})")
MONTH_NAME = re.compile(r"([a-z]+)(?:\s+(?:de\s+)?(\d{4}))?")
LAST_DAYS = re.compile(r"ultimos?\s+(\d+)\s+dias?(\s+(?:uteis|util))?")


class PeriodError(ValueError):
    """The text is not a period; the message lists the accepted forms."""


@dataclass(frozen=True)
class Period:
    since: date
    until: date
    label: str
    workdays: int
    warnings: tuple[str, ...]


def _normalize(text: str) -> str:
    plain = unicodedata.normalize("NFD", text.lower())
    plain = "".join(char for char in plain if not unicodedata.combining(char))
    words = plain.split()
    while len(words) > 1 and words[0] in LEADING:
        words.pop(0)
    return " ".join(words)


def _fail(text: str, reason: str | None = None) -> PeriodError:
    head = reason or f"unknown period {text!r}"
    return PeriodError(f"{head}; accepted forms: {ACCEPTED_FORMS}")


def _latest_day(day: int, month: int, not_after: date) -> date | None:
    for year in range(not_after.year, not_after.year - 9, -1):
        try:
            found = date(year, month, day)
        except ValueError:
            continue
        if found <= not_after:
            return found
    return None


def _parse_day(raw_day: str, not_after: date, text: str) -> date:
    if "-" in raw_day:
        try:
            return date.fromisoformat(raw_day)
        except ValueError:
            raise _fail(text, f"invalid date {raw_day!r}") from None
    parts = raw_day.split("/")
    day, month = int(parts[0]), int(parts[1])
    if len(parts) == 3:
        try:
            return date(int(parts[2]), month, day)
        except ValueError:
            raise _fail(text, f"invalid date {raw_day!r}") from None
    found = _latest_day(day, month, not_after)
    if found is None:
        raise _fail(text, f"invalid date {raw_day!r}")
    return found


def _count_workdays(since: date, until: date) -> int:
    days = (until - since).days + 1
    return sum(1 for i in range(days) if (since + timedelta(days=i)).weekday() not in WEEKEND_DAYS)


def _short(day: date, with_year: bool) -> str:
    return day.strftime("%d/%m/%Y" if with_year else "%d/%m")


def _span(since: date, until: date, today: date) -> str:
    with_year = since.year != until.year or until.year != today.year
    if since == until:
        return _short(since, with_year)
    return f"{_short(since, with_year)} a {_short(until, with_year)}"


def _month_index(word: str) -> int | None:
    if word in MONTHS:
        return MONTHS.index(word) + 1
    if word in MONTH_ABBREVIATIONS:
        return MONTH_ABBREVIATIONS.index(word) + 1
    return None


def _month(year: int, month: int, today: date) -> tuple[date, date, str]:
    first = date(year, month, 1)
    last = date(year, month, monthrange(year, month)[1])
    return first, last, f"{MONTH_LABELS[month - 1]} de {year} ({_span(first, last, today)})"


def _last_days(match: re.Match, today: date, text: str) -> tuple[date, date, str]:
    count = int(match.group(1))
    if count < 1:
        raise _fail(text, "the number of days must be at least 1")
    if count > MAX_DAYS:
        raise _fail(text, f"the window is over {MAX_DAYS} days")
    if match.group(2):
        # Today counts as one of the N when it is a workday.
        back = count if today.weekday() in WEEKEND_DAYS else count - 1
        since = workdays_before(today, back)
        return since, today, f"últimos {count} dias úteis ({_span(since, today, today)})"
    since = today - timedelta(days=count - 1)
    return since, today, f"últimos {count} dias ({_span(since, today, today)})"


def _resolve(norm: str, today: date, text: str) -> tuple[date, date, str]:
    if norm == "hoje":
        return today, today, f"hoje ({_short(today, False)})"
    if norm == "ontem":
        day = workdays_before(today, 1)
        return day, day, f"ontem ({_short(day, day.year != today.year)})"
    if norm in ("esta semana", "essa semana", "semana atual"):
        monday = today - timedelta(days=today.weekday())
        return monday, today, f"esta semana ({_span(monday, today, today)})"
    if norm in ("semana passada", "ultima semana"):
        monday = today - timedelta(days=today.weekday() + 7)
        sunday = monday + timedelta(days=6)
        return monday, sunday, f"semana passada ({_span(monday, sunday, today)})"
    if norm in ("este mes", "esse mes", "mes atual"):
        first = today.replace(day=1)
        return first, today, f"este mês ({_span(first, today, today)})"
    if norm == "mes passado":
        last_day = today.replace(day=1) - timedelta(days=1)
        first = last_day.replace(day=1)
        return first, last_day, f"mês passado ({_span(first, last_day, today)})"
    if match := LAST_DAYS.fullmatch(norm):
        return _last_days(match, today, text)
    if match := SINCE_DAY.fullmatch(norm):
        since = _parse_day(match.group(1), today, text)
        return since, today, f"desde {_short(since, since.year != today.year)}"
    if match := RANGE.fullmatch(norm):
        until = _parse_day(match.group(2), today, text)
        start = _parse_day(match.group(1), until, text)
        return start, until, _span(start, until, today)
    if match := MONTH_YEAR.fullmatch(norm):
        month, year = int(match.group(1)), int(match.group(2))
        if not 1 <= month <= 12:
            raise _fail(text, f"invalid month {month}")
        return _month(year, month, today)
    if (match := MONTH_NAME.fullmatch(norm)) and (month := _month_index(match.group(1))):
        if match.group(2):
            year = int(match.group(2))
        else:
            year = today.year if month <= today.month else today.year - 1
        return _month(year, month, today)
    if match := ONE_DAY.fullmatch(norm):
        day = _parse_day(match.group(1), today, text)
        return day, day, f"dia {_short(day, day.year != today.year)}"
    raise _fail(text)


def parse_period(text: str, today: date) -> Period:
    norm = _normalize(text)
    if not norm:
        raise _fail(text, "empty period")
    since, until, label = _resolve(norm, today, text)
    warnings: list[str] = []
    if until > today:
        warnings.append(f"the end of the period is after today: clipped to {today.isoformat()}")
        until = today
        label = f"{label}, até hoje"
    if since > until:
        raise _fail(text, "the start of the period is after its end")
    if (until - since).days + 1 > MAX_DAYS:
        raise _fail(
            text,
            f"the window is over {MAX_DAYS} days (a day written without a year is the latest one "
            "before the end: write the years if you meant another range)",
        )
    return Period(since, until, label, _count_workdays(since, until), tuple(warnings))
