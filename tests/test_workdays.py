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


def test_national_holidays():
    from ws.workdays import national_holidays

    h2026 = national_holidays(2026)
    for day in [(2, 16), (2, 17), (4, 3), (6, 4), (11, 20), (12, 25), (1, 1), (11, 15)]:
        assert date(2026, *day) in h2026
    h2027 = national_holidays(2027)
    for day in [(2, 8), (2, 9), (3, 26), (5, 27)]:
        assert date(2027, *day) in h2027


def test_business_days_skip_weekends_and_holidays():
    from ws.workdays import is_business_day, next_business_day
    from ws.workdays import previous_business_day as previous_bd

    assert previous_bd(date(2026, 12, 28)) == date(2026, 12, 24)
    assert is_business_day(date(2026, 12, 25)) is False
    assert is_business_day(date(2026, 12, 24)) is True
    assert is_business_day(date(2026, 12, 24), frozenset({date(2026, 12, 24)})) is False
    assert next_business_day(date(2026, 12, 24)) == date(2026, 12, 28)
    assert previous_workday(date(2026, 12, 28)) == date(2026, 12, 25)


def test_business_days_range_is_after_exclusive_until_inclusive():
    from ws.workdays import business_days

    assert business_days(date(2026, 12, 8), date(2026, 12, 15)) == [
        date(2026, 12, 9),
        date(2026, 12, 10),
        date(2026, 12, 11),
        date(2026, 12, 14),
        date(2026, 12, 15),
    ]
    assert business_days(date(2026, 12, 15), date(2026, 12, 15)) == []


def test_extra_holidays_from_config(tmp_path, monkeypatch):
    from ws.userconfig import ConfigInvalid
    from ws.workdays import extra_holidays

    monkeypatch.setenv("WS_CONFIG_DIR", str(tmp_path))
    assert extra_holidays() == frozenset()
    (tmp_path / "config.toml").write_text('[workdays]\nholidays = [2026-12-24, "2026-12-31"]\n')
    assert extra_holidays() == frozenset({date(2026, 12, 24), date(2026, 12, 31)})
    (tmp_path / "config.toml").write_text('[workdays]\nholidays = [2026-12-24, "x"]\n')
    with pytest.raises(ConfigInvalid, match=r"workdays\.holidays\[1\] must be a YYYY-MM-DD date"):
        extra_holidays()
    (tmp_path / "config.toml").write_text("[jira]\n")
    assert extra_holidays() == frozenset()


def test_movable_holidays_are_not_business_days():
    from ws.workdays import is_business_day, next_business_day

    assert is_business_day(date(2027, 2, 8)) is False
    assert is_business_day(date(2027, 2, 9)) is False
    assert is_business_day(date(2027, 3, 26)) is False
    assert is_business_day(date(2027, 5, 27)) is False
    assert is_business_day(date(2026, 6, 4)) is False
    assert next_business_day(date(2027, 2, 5)) == date(2027, 2, 10)
