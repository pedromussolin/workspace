"""Claude Code PreToolUse hook: makes Claude Code ask the user before a card approval can run.

`ws card apply --approve CODE` writes to Jira, and the user's yes in Claude Code's own prompt is
the approval. A `permissions.ask` rule matches the command text, so a wrapper (`uv run ws ...`,
`python -m ws ...`, an absolute path to `ws`) would skip it, and so would shell tricks inside the
flag (`--appr$(true)ove`, a variable holding `--approve`). This hook asks for any Bash command
that, after quotes and backslashes are removed, has `card` and `apply` as words, or `ws.card`,
or `from ws import card`, or `run_apply`. It does not look for `--approve`: `apply` without it
only exits 1, and `preview`, `check` and `epics` stay silent.

The limit: it reads text. A script file the command runs, or an import route that matches none of
those patterns, is not seen. The `ws card apply --approve` refusal without this hook registered,
and the review of what Claude runs, cover the rest.

Anything the hook cannot read also asks: it never fails open.
"""

import json
import re
import sys

QUOTING = re.compile(r"[\"'\\]")
CARD = re.compile(r"\bcard\b")
APPLY = re.compile(r"\bapply\b")
OTHER_ROUTES = re.compile(r"ws\.card|from\s+ws\s+import\s+card|run_apply")

REASON = (
    "This command may apply a card approval (ws card apply --approve): it writes to Jira. "
    "Your yes in this prompt is the approval."
)


def applies_an_approval(command: str) -> bool:
    plain = QUOTING.sub("", command)
    if CARD.search(plain) and APPLY.search(plain):
        return True
    return OTHER_ROUTES.search(plain) is not None


def ask(reason: str) -> None:
    output = {
        "hookSpecificOutput": {
            "hookEventName": "PreToolUse",
            "permissionDecision": "ask",
            "permissionDecisionReason": reason,
        }
    }
    print(json.dumps(output))


def main() -> int:
    try:
        payload = json.load(sys.stdin)
        command = payload.get("tool_input", {}).get("command", "")
        if not isinstance(command, str):
            raise TypeError("tool_input.command is not a string")
    except Exception as error:
        ask(f"The card approval hook could not read the tool input ({error}); asking to be safe.")
        return 0
    if applies_an_approval(command):
        ask(REASON)
    return 0


if __name__ == "__main__":
    sys.exit(main())
