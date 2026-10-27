from datetime import date

import pytest

from ws.workdays import previous_workday, workdays_before


@pytest.mark.parametrize(
    "day, expected",
    [
        (date(2026, 10, 26), date(2026, 10, 23)),  # Monday -> Friday
        (date(2026, 10, 27), date(2026, 10, 26)),  # Tuesday -> Monday
        (date(2026, 10, 24), date(2026, 10, 23)),  # Saturday -> Friday
        (date(2026, 10, 25), date(2026, 10, 23)),  # Sunday -> Friday
    ],
)
def test_previous_workday(day, expected):
    assert previous_workday(day) == expected


def test_workdays_before_skips_weekends():
    assert workdays_before(date(2026, 10, 27), 3) == date(2026, 10, 22)


def test_workdays_before_zero_is_the_same_day():
    assert workdays_before(date(2026, 10, 27), 0) == date(2026, 10, 27)
