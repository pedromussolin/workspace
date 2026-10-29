"""The gate's decision and the PT-BR text of the approval box: the contract every rule shares.

A rule returns `PASS` (the normal permission flow goes on), `ask(...)` (Claude Code shows the box
with this text) or `deny(...)` (blocked; the reason goes to the model). The box text is built
here only, from values taken out of the real call, so its shape changes in one place.
"""

import json
from dataclasses import dataclass

MAX_LINES = 10
MAX_WIDTH = 160
FOOTER = '"Yes" aprova só esta chamada.'


@dataclass(frozen=True)
class Decision:
    kind: str
    reason: str = ""


PASS = Decision("pass")


def cut(text: str, width: int = MAX_WIDTH) -> str:
    """One line: whitespace runs collapsed, cut at `width` with an ellipsis."""
    flat = " ".join(str(text).split())
    return flat if len(flat) <= width else flat[: width - 1] + "…"


def body_summary(text: str) -> str:
    """A long text as its line count and first non-empty line, e.g. `3 linhas (primeira: "…")`."""
    lines = [line for line in str(text).splitlines() if line.strip()]
    if not lines:
        return "vazio"
    count = "1 linha" if len(lines) == 1 else f"{len(lines)} linhas"
    return f'{count} (primeira: "{cut(lines[0], 80)}")'


def ask_text(title: str, lines: list[str]) -> str:
    body = [cut(line) for line in lines if str(line).strip()]
    room = MAX_LINES - 2
    if len(body) > room:
        body = body[: room - 1] + [f"(+{len(body) - room + 1} linhas)"]
    return "\n".join([cut(title), *body, FOOTER])


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
