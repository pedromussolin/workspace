"""The card side of the review pack: the card and its "Pronto quando" section."""

import re

from ws.cardrules import fold
from ws.tracker.port import Tracker

_HEADING = re.compile(r"^#+\s+(.*)$")
_SECTION = "pronto quando"


def done_when(text: str) -> str | None:
    lines: list[str] = []
    inside = False
    for line in text.splitlines():
        heading = _HEADING.match(line.strip())
        if heading:
            if inside:
                break
            inside = fold(heading.group(1)) == _SECTION
            continue
        if inside:
            lines.append(line)
    return "\n".join(lines).strip() or None


def card_context(tracker: Tracker, ref: str) -> tuple[dict | None, list[str]]:
    card = tracker.card(ref)
    if card is None:
        return None, []
    warnings: list[str] = []
    section = None
    if "description" not in tracker.capabilities:
        warnings.append("the tracker gives no card description; read Pronto quando in the tracker")
    else:
        text = tracker.description(ref)
        section = done_when(text) if text else None
        if section is None:
            warnings.append(f"{ref} has no Pronto quando section")
    context = {
        "ref": card.ref,
        "title": card.title,
        "type": card.type,
        "status": card.status.value,
        "done_when": section,
    }
    return context, warnings
