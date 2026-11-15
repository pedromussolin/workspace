"""Dias úteis: `workdays_before` e `previous_workday` só pulam fins de semana (standup, daily);
`is_business_day` e as demais também pulam feriados nacionais, os móveis dos bancos e os do config.
"""

import re
from datetime import date, timedelta
from functools import cache

from ws.userconfig import ConfigInvalid, ConfigMissing, load_table

WEEKEND_DAYS = (5, 6)


def workdays_before(day: date, n: int) -> date:
    current = day
    remaining = n
    while remaining > 0:
        current -= timedelta(days=1)
        if current.weekday() not in WEEKEND_DAYS:
            remaining -= 1
    return current


def previous_workday(day: date) -> date:
    return workdays_before(day, 1)


FIXED_HOLIDAYS = ((1, 1), (4, 21), (5, 1), (9, 7), (10, 12), (11, 2), (11, 15), (11, 20), (12, 25))
ISO_DATE = re.compile(r"\d{4}-\d{2}-\d{2}")


def easter(year: int) -> date:
    a = year % 19
    b, c = divmod(year, 100)
    d, e = divmod(b, 4)
    f = (b + 8) // 25
    g = (b - f + 1) // 3
    h = (19 * a + b - d - g + 15) % 30
    i, k = divmod(c, 4)
    n = (32 + 2 * e + 2 * i - h - k) % 7
    m = (a + 11 * h + 22 * n) // 451
    month, offset = divmod(h + n - 7 * m + 114, 31)
    return date(year, month, offset + 1)


@cache
def national_holidays(year: int) -> frozenset[date]:
    base = easter(year)
    movable = (
        base - timedelta(days=48),
        base - timedelta(days=47),
        base - timedelta(days=2),
        base + timedelta(days=60),
    )
    return frozenset({date(year, month, day) for month, day in FIXED_HOLIDAYS} | set(movable))


def _holiday(index: int, item: object) -> date:
    if isinstance(item, date):
        return item
    if isinstance(item, str) and ISO_DATE.fullmatch(item):
        try:
            return date.fromisoformat(item)
        except ValueError:
            pass
    raise ConfigInvalid(f"workdays.holidays[{index}] must be a YYYY-MM-DD date")


def extra_holidays() -> frozenset[date]:
    try:
        table = load_table("workdays")
    except ConfigMissing:
        return frozenset()
    items = table.get("holidays", [])
    if not isinstance(items, list):
        raise ConfigInvalid("workdays.holidays must be a list of YYYY-MM-DD dates")
    return frozenset(_holiday(index, item) for index, item in enumerate(items))


def is_business_day(day: date, extra: frozenset[date] = frozenset()) -> bool:
    return (
        day.weekday() not in WEEKEND_DAYS
        and day not in national_holidays(day.year)
        and day not in extra
    )


def previous_business_day(day: date, extra: frozenset[date] = frozenset()) -> date:
    current = day - timedelta(days=1)
    while not is_business_day(current, extra):
        current -= timedelta(days=1)
    return current


def next_business_day(day: date, extra: frozenset[date] = frozenset()) -> date:
    current = day + timedelta(days=1)
    while not is_business_day(current, extra):
        current += timedelta(days=1)
    return current


def business_days(after: date, until: date, extra: frozenset[date] = frozenset()) -> list[date]:
    days = []
    current = after + timedelta(days=1)
    while current <= until:
        if is_business_day(current, extra):
            days.append(current)
        current += timedelta(days=1)
    return days
