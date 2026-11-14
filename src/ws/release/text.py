"""Dates, task keys and the merge commit texts of the release."""

import re
from datetime import date

from ws.release import ReleaseRefused

TASK_KEY = re.compile(r"\bTS-\d+\b")
SUBJECT = re.compile(r"^(feat|chore|refact|fix|test)\(TS-\d+(, TS-\d+)*\): .+")
MAX_SUBJECT = 72
MASTER_TEXT = "atualiza com a master"
_DAY = re.compile(r"(\d{4})-?(\d{2})-?(\d{2})")
_SEPARATORS = "-/"


def sandbox_text(code: str) -> str:
    return f"junta a {code} na sandbox"


def copy_text(code: str) -> str:
    return f"atualiza a cópia com a {code}"


def today() -> date:
    return date.today()


def parse_day(text: str) -> date:
    match = _DAY.fullmatch(text)
    if match is None or ("-" in text) != (len(text) == 10):
        raise ValueError(f"{text!r} is not a day: use YYYYMMDD or YYYY-MM-DD")
    return date(*(int(part) for part in match.groups()))


def future_day(text: str) -> date:
    day = parse_day(text)
    if day < today():
        raise ReleaseRefused(f"{compact(day)} is in the past")
    return day


def compact(day: date) -> str:
    return day.strftime("%Y%m%d")


def display(day: date) -> str:
    return day.strftime("%d/%m/%Y")


def keys_of(text: str) -> list[str]:
    return list(dict.fromkeys(TASK_KEY.findall(text)))


def _cut_on_word(text: str, room: int) -> str:
    if len(text) <= room:
        return text
    head = text[:room]
    if text[room] in _SEPARATORS + " ":
        return head
    cut = max(head.rfind(mark) for mark in _SEPARATORS + " ")
    return head[:cut] if cut > 0 else head


def task_merge_subject(key: str, branch: str) -> str:
    prefix = f"chore({key}): junta a "
    return prefix + _cut_on_word(branch, MAX_SUBJECT - len(prefix))


def release_merge_message(keys: list[str], text: str) -> tuple[str, str]:
    first_word = text.split()[0]

    def scope(count: int) -> str:
        return f"chore({', '.join(keys[:count])}): "

    count = len(keys)
    while count > 1 and len(scope(count)) + len(first_word) > MAX_SUBJECT:
        count -= 1
    subject = scope(count) + first_word
    for word in text.split()[1:]:
        if len(subject) + 1 + len(word) > MAX_SUBJECT:
            break
        subject += f" {word}"
    body = f"Tarefas: {', '.join(keys)}" if count < len(keys) else ""
    return subject, body
