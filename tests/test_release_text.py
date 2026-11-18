import re
from datetime import date

import pytest

from ws.release import ReleaseRefused, ReleaseSetup, text
from ws.release.text import (
    MASTER_TEXT,
    SUBJECT,
    compact,
    copy_text,
    display,
    environment_text,
    future_day,
    keys_of,
    parse_day,
    release_merge_message,
    task_merge_subject,
)


@pytest.fixture(autouse=True)
def fixed_today(monkeypatch):
    monkeypatch.setattr(text, "today", lambda: date(2026, 11, 13))


def test_parse_day_accepts_both_forms():
    assert parse_day("20261120") == date(2026, 11, 20)
    assert parse_day("2026-11-20") == date(2026, 11, 20)


@pytest.mark.parametrize("bad", ["20/11/2026", "2026112", "20261340", ""])
def test_parse_day_refuses_others(bad):
    with pytest.raises(ValueError):
        parse_day(bad)


def test_future_day_refuses_the_past():
    with pytest.raises(ReleaseRefused, match="20261112 is in the past"):
        future_day("20261112")
    assert future_day("20261113") == date(2026, 11, 13)


def test_display_and_compact():
    day = date(2026, 11, 20)
    assert display(day) == "20/11/2026"
    assert compact(day) == "20261120"


def test_keys_of():
    assert keys_of("UTF-8 TS-12 e TS-12, TS-3") == ["TS-12", "TS-3"]


def test_release_texts():
    assert MASTER_TEXT == "atualiza com a master"
    assert environment_text("release/20261120", "sandbox") == "junta a release/20261120 na sandbox"
    assert copy_text("release/20261120") == "atualiza a cópia com a release/20261120"


def test_task_merge_subject_short():
    assert (
        task_merge_subject("TS-101", "feature/TS-101-one")
        == "chore(TS-101): junta a feature/TS-101-one"
    )


def test_task_merge_subject_cuts_the_branch_on_a_word():
    subject = task_merge_subject("TS-101", "feature/TS-101-um-nome-de-branch-bem-longo-para-cortar")

    assert subject == "chore(TS-101): junta a feature/TS-101-um-nome-de-branch-bem-longo-para"
    assert len(subject) == 70
    assert re.match(SUBJECT, subject)


def test_release_merge_message_keeps_six_keys():
    keys = [f"TS-100{n}" for n in range(1, 7)]

    subject, body = release_merge_message(keys, MASTER_TEXT)

    assert subject == "chore(TS-1001, TS-1002, TS-1003, TS-1004, TS-1005, TS-1006): atualiza"
    assert body == ""


def test_release_merge_message_moves_extra_keys_to_the_body():
    keys = [f"TS-100{n}" for n in range(1, 8)]

    subject, body = release_merge_message(keys, MASTER_TEXT)

    assert subject.startswith("chore(TS-1001, TS-1002, TS-1003, TS-1004, TS-1005, TS-1006): ")
    assert "TS-1007" not in subject
    assert len(subject) <= 72
    assert re.match(SUBJECT, subject)
    assert body == "Tarefas: " + ", ".join(keys)


def test_release_merge_message_keeps_the_whole_text_when_it_fits():
    subject, body = release_merge_message(["TS-1", "TS-2"], MASTER_TEXT)

    assert subject == "chore(TS-1, TS-2): atualiza com a master"
    assert body == ""


def test_day_argument_maps_a_malformed_day_to_a_setup_problem():
    assert text.day_argument("2026-11-20") == date(2026, 11, 20)
    with pytest.raises(ReleaseSetup, match="is not a day"):
        text.day_argument("2026-1120")


@pytest.mark.parametrize("count", [5, 6, 7, 9, 12])
@pytest.mark.parametrize(
    "words",
    [
        MASTER_TEXT,
        environment_text("release/20261120", "sandbox"),
        copy_text("feature/TS-5416-tela-com-filtro"),
    ],
)
def test_release_merge_message_never_ends_in_a_function_word(count, words):
    keys = [f"TS-{5400 + n}" for n in range(count)]

    subject, _ = release_merge_message(keys, words)

    assert len(subject) <= 72 and SUBJECT.match(subject)
    assert subject.split()[-1] not in {"a", "o", "com", "na", "no", "da", "do", "de", "e"}


def test_release_merge_message_drops_the_dangling_words():
    keys = [f"TS-{5400 + n}" for n in range(5)]

    assert release_merge_message(keys, MASTER_TEXT)[0].endswith("): atualiza")
    assert release_merge_message(keys, environment_text("release/20261120", "sandbox"))[0].endswith(
        "): junta"
    )
