import json
from datetime import date

import pytest

from ws.cli import main
from ws.period import PeriodError, parse_period

MONDAY = date(2026, 11, 2)
TUESDAY = date(2026, 11, 3)


def span(text, today=TUESDAY):
    period = parse_period(text, today)
    return period.since.isoformat(), period.until.isoformat()


def test_last_week_is_monday_to_sunday():
    period = parse_period("semana passada", TUESDAY)
    assert (period.since, period.until) == (date(2026, 10, 26), date(2026, 11, 1))
    assert period.workdays == 5
    assert period.warnings == ()
    assert span("última semana") == ("2026-10-26", "2026-11-01")


def test_this_week_is_monday_to_today():
    assert span("esta semana") == ("2026-11-02", "2026-11-03")
    assert span("essa semana", MONDAY) == ("2026-11-02", "2026-11-02")
    assert span("semana atual") == ("2026-11-02", "2026-11-03")


def test_month_without_year_is_latest_started():
    assert span("outubro") == ("2026-10-01", "2026-10-31")
    assert span("out") == ("2026-10-01", "2026-10-31")
    assert span("novembro")[0] == "2026-11-01"


def test_month_not_started_this_year_is_last_year():
    assert span("dezembro") == ("2025-12-01", "2025-12-31")
    assert span("fevereiro", date(2026, 1, 15)) == ("2025-02-01", "2025-02-28")


def test_month_with_year_and_numeric_form():
    assert span("outubro de 2026") == ("2026-10-01", "2026-10-31")
    assert span("10/2026") == ("2026-10-01", "2026-10-31")
    assert span("março 2024") == ("2024-03-01", "2024-03-31")
    assert span("fev de 2024") == ("2024-02-01", "2024-02-29")


def test_this_month_and_last_month():
    assert span("este mês") == ("2026-11-01", "2026-11-03")
    assert span("esse mês") == ("2026-11-01", "2026-11-03")
    assert span("mês passado") == ("2026-10-01", "2026-10-31")
    assert span("mês passado", date(2026, 1, 9)) == ("2025-12-01", "2025-12-31")


def test_last_n_days_and_last_n_workdays():
    assert span("últimos 7 dias") == ("2026-10-28", "2026-11-03")
    period = parse_period("últimos 3 dias úteis", TUESDAY)
    assert (period.since, period.until, period.workdays) == (
        date(2026, 10, 30),
        TUESDAY,
        3,
    )
    sunday = parse_period("últimos 2 dias úteis", date(2026, 11, 1))
    assert (sunday.since.isoformat(), sunday.workdays) == ("2026-10-29", 2)


def test_range_without_year_infers_before_end():
    assert span("20/10 a 31/10") == ("2026-10-20", "2026-10-31")
    assert span("de 20/10 até 31/10") == ("2026-10-20", "2026-10-31")
    assert span("20/10 a 02/11") == ("2026-10-20", "2026-11-02")


def test_range_across_new_year():
    assert span("20/12 a 05/01", date(2027, 1, 10)) == ("2026-12-20", "2027-01-05")


def test_iso_range():
    assert span("2026-10-20..2026-10-31") == ("2026-10-20", "2026-10-31")
    assert span("20/10/2026 a 31/10/2026") == ("2026-10-20", "2026-10-31")


def test_single_day_and_since_day():
    assert span("20/10") == ("2026-10-20", "2026-10-20")
    assert span("desde 20/10") == ("2026-10-20", "2026-11-03")
    assert span("25/12") == ("2025-12-25", "2025-12-25")


def test_today_and_yesterday_is_previous_workday():
    assert span("hoje") == ("2026-11-03", "2026-11-03")
    assert span("ontem") == ("2026-11-02", "2026-11-02")
    assert span("ontem", MONDAY) == ("2026-10-30", "2026-10-30")


def test_accents_case_and_leading_words():
    assert span("  Da   SEMANA Passada ") == ("2026-10-26", "2026-11-01")
    assert span("no mês passado") == ("2026-10-01", "2026-10-31")
    assert span("em Outubro") == ("2026-10-01", "2026-10-31")
    assert span("ULTIMOS 7 DIAS") == ("2026-10-28", "2026-11-03")
    assert span("Março de 2025") == ("2025-03-01", "2025-03-31")


def test_until_after_today_is_clipped_with_warning():
    period = parse_period("novembro", TUESDAY)
    assert period.until == TUESDAY
    assert len(period.warnings) == 1
    assert "clipped" in period.warnings[0]
    assert parse_period("20/10/2026 a 30/11/2026", TUESDAY).until == TUESDAY


def test_over_120_days_is_refused():
    with pytest.raises(PeriodError, match="120"):
        parse_period("01/01/2026 a 03/11/2026", TUESDAY)
    with pytest.raises(PeriodError, match="120"):
        parse_period("últimos 200 dias", TUESDAY)


def test_since_after_until_is_refused():
    with pytest.raises(PeriodError, match="after"):
        parse_period("2026-10-31..2026-10-20", TUESDAY)
    with pytest.raises(PeriodError, match="after"):
        parse_period("desde 2026-12-01", TUESDAY)


def test_unknown_text_lists_the_forms():
    for text in ("quando der", "", "31/02", "13/2026"):
        with pytest.raises(PeriodError, match="accepted forms"):
            parse_period(text, TUESDAY)


def test_label_is_ptbr():
    assert parse_period("semana passada", TUESDAY).label == "semana passada (26/10 a 01/11)"
    assert parse_period("outubro", TUESDAY).label == "outubro de 2026 (01/10 a 31/10)"
    assert parse_period("março 2025", TUESDAY).label == "março de 2025 (01/03/2025 a 31/03/2025)"
    assert parse_period("últimos 7 dias", TUESDAY).label == "últimos 7 dias (28/10 a 03/11)"
    assert parse_period("20/10 a 31/10", TUESDAY).label == "20/10 a 31/10"
    assert parse_period("ontem", TUESDAY).label == "ontem (02/11)"
    assert parse_period("novembro", TUESDAY).label.endswith(", até hoje")


def test_cli_period_prints_json(capsys):
    assert main(["standup", "period", "semana passada", "--today", "2026-11-03"]) == 0
    assert json.loads(capsys.readouterr().out) == {
        "since": "2026-10-26",
        "until": "2026-11-01",
        "label": "semana passada (26/10 a 01/11)",
        "workdays": 5,
        "warnings": [],
    }


def test_cli_period_unknown_exits_2(capsys):
    assert main(["standup", "period", "quando der", "--today", "2026-11-03"]) == 2
    captured = capsys.readouterr()
    assert captured.out == ""
    assert "accepted forms" in captured.err
