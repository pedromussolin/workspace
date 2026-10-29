"""The gate's decision and the PT-BR text of the approval box: the contract every rule shares.

A rule returns `PASS` (the normal permission flow goes on), `ask(...)` (Claude Code shows the box
with this text) or `deny(...)` (blocked; the reason goes to the model). The box text is built
here only, from values taken out of the real call, so its shape changes in one place.

The box holds at most `MAX_LINES` lines, but a line that starts with `ATENÇÃO:` is a warning the
user must not miss: it goes right after the title, keeps its order among the others and is never
cut nor folded into "(+N linhas)". The other lines fill what is left; if the warnings alone exceed
the room, all of them stay (a longer box beats a hidden warning).
"""

import json
import sys
import unicodedata
from dataclasses import dataclass

MAX_LINES = 10
MAX_WIDTH = 160
FOOTER = '"Yes" aprova só esta chamada.'
WARNING_PREFIX = "ATENÇÃO:"
REPLACEMENT = "\ufffd"


@dataclass(frozen=True)
class Decision:
    kind: str
    reason: str = ""


PASS = Decision("pass")


def cut(text: str, width: int = MAX_WIDTH) -> str:
    """One line: whitespace runs collapsed, control and format characters (ESC, bidi overrides,
    zero-width) shown as `�`, cut at `width` with an ellipsis."""
    flat = "".join(
        REPLACEMENT if unicodedata.category(char) in ("Cc", "Cf") else char
        for char in " ".join(str(text).split())
    )
    return flat if len(flat) <= width else flat[: width - 1] + "…"


def body_summary(text: str) -> str:
    """A long text as its line count and first non-empty line, e.g. `3 linhas (primeira: "…")`."""
    lines = [line for line in str(text).splitlines() if line.strip()]
    if not lines:
        return "vazio"
    count = "1 linha" if len(lines) == 1 else f"{len(lines)} linhas"
    return f'{count} (primeira: "{cut(lines[0], 80)}")'


def ask_text(title: str, lines: list[str]) -> str:
    flat = [cut(line, sys.maxsize) for line in lines if str(line).strip()]
    warnings = [line for line in flat if line.startswith(WARNING_PREFIX)]
    rest = [cut(line) for line in flat if not line.startswith(WARNING_PREFIX)]
    room = MAX_LINES - 2 - len(warnings)
    if len(rest) > room:
        keep = max(room - 1, 0)
        rest = rest[:keep] + [f"(+{len(rest) - keep} linhas)"]
    return "\n".join([cut(title), *warnings, *rest, FOOTER])


def ask(title: str, lines: list[str]) -> Decision:
    return Decision("ask", ask_text(title, lines))


def deny(reason: str) -> Decision:
    return Decision("deny", reason)


def to_output(decision: Decision) -> str | None:
    """The hook's stdout for a decision; None means print nothing."""
    if decision.kind == "pass":
        return None
    return json.dumps(
        {
            "hookSpecificOutput": {
                "hookEventName": "PreToolUse",
                "permissionDecision": decision.kind,
                "permissionDecisionReason": decision.reason,
            }
        },
        ensure_ascii=False,
    )
