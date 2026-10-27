"""Dias úteis (segunda a sexta) para o standup; feriados ainda não são considerados."""

from datetime import date, timedelta

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
