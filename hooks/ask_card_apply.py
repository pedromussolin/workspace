"""Claude Code PreToolUse hook: makes Claude Code ask the user before a card approval runs.

`ws card apply --approve CODE` writes to Jira, and the user's yes in Claude Code's own prompt is
the approval. A `permissions.ask` rule matches the command text, so a wrapper (`uv run ws ...`,
`python -m ws ...`, `bash -c '...'`, an absolute path to `ws`, quotes inside a flag) would skip
it. This hook decides on the meaning instead: any Bash command that has `--approve` and either
`card` with `apply`, or `ws.card`, gets `permissionDecision: "ask"`, however it is written.

Anything the hook cannot read also asks: it never fails open.
"""

import json
import re
import sys

QUOTING = re.compile(r"[\"'\\]")
CARD = re.compile(r"\bcard\b")
APPLY = re.compile(r"\bapply\b")
CARD_MODULE = re.compile(r"ws.card")

REASON = (
    "This command applies a card approval (ws card apply --approve): it writes to Jira. "
    "Your yes in this prompt is the approval."
)


def applies_an_approval(command: str) -> bool:
    plain = QUOTING.sub("", command)
    if "--approve" not in plain:
        return False
    return bool(CARD.search(plain) and APPLY.search(plain)) or bool(CARD_MODULE.search(plain))


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
