"""The gate's decision and the PT-BR text of the approval box: the contract every rule shares.

A rule returns `PASS` (the normal permission flow goes on), `ask(...)` (Claude Code shows the box
with this text) or `deny(...)` (blocked; the reason goes to the model). The box text is built
here only, from values taken out of the real call, so its shape changes in one place.

The box is short: a title that says what is at stake, then at most `MAX_LINES - 1` lines, each
`<reason> — `<the piece of the command that triggered it>``, so the user finds the trigger in the
command Claude Code already shows above the box. There is no footer and the box never repeats the
command. A line that starts with `ATENÇÃO:` is a real danger the user must not miss: it goes right
after the title, keeps its order among the others and is never cut nor folded into "(+N linhas)".
The other lines fill what is left; if the warnings alone exceed the room, all of them stay (a
longer box beats a hidden warning).
"""

import json
import sys
import unicodedata
from dataclasses import dataclass

MAX_LINES = 4
MAX_WIDTH = 100
TITLE_WIDTH = 60
TRIGGER_WIDTH = 50
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


def trigger(text: str, width: int = TRIGGER_WIDTH) -> str:
    """The piece of the command that triggered a reason, cut short, in backticks."""
    return f"`{cut(text.replace('`', "'"), width)}`"


def body_summary(text: str) -> str:
    """A long text as its line count and first non-empty line, e.g. `3 linhas (primeira: "…")`."""
    lines = [line for line in str(text).splitlines() if line.strip()]
    if not lines:
        return "vazio"
    count = "1 linha" if len(lines) == 1 else f"{len(lines)} linhas"
    return f'{count} (primeira: "{cut(lines[0], 40)}")'


def ask_text(title: str, lines: list[str]) -> str:
    flat = list(dict.fromkeys(cut(line, sys.maxsize) for line in lines if str(line).strip()))
    warnings = [line for line in flat if line.startswith(WARNING_PREFIX)]
    rest = [cut(line) for line in flat if not line.startswith(WARNING_PREFIX)]
    room = MAX_LINES - 1 - len(warnings)
    if len(rest) > room:
        keep = max(room - 1, 0)
        rest = rest[:keep] + [f"(+{len(rest) - keep} linhas)"]
    return "\n".join([cut(title, TITLE_WIDTH), *warnings, *rest])


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
