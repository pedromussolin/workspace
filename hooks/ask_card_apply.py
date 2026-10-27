"""Claude Code PreToolUse hook: makes Claude Code ask the user before a card approval can run.

`ws card apply --approve CODE` writes to Jira, and the user's yes in Claude Code's own prompt is
the approval. A `permissions.ask` rule matches the command text, so a wrapper (`uv run ws ...`,
`python -m ws ...`, an absolute path to `ws`) would skip it, and so would shell tricks that build
the words (`--appr$(true)ove`, `ap${x}ply`, `a{pp,pp}ly`, `$'\\x61pply'`, a backslash-newline).
This hook asks when, after quotes and backslashes are removed, the command has `card` and `apply`
as words, or `ws.card`, `from ws import card` or `run_apply`; and also when it has `ws` or `card`
as a word together with a shell expansion or escape (`$`, a backtick, `{`, a backslash-newline)
or `eval`, `base64`, `xxd`, `printf`. It does not look for `--approve`: `apply` without it only
exits 1, and a plain `preview`, `check` or `epics` stays silent.

Two things do not depend on text: `ws card apply --approve` exits 2 without this hook registered,
and it refuses (exit 1) to run in the same shell session as the preview.

The limit: it reads text. A script file the command runs, a background process in a new session
(`setsid`, `nohup`) or an import route that matches none of those patterns is not seen; there the
auto-mode classifier and the user's reading of each command remain the barrier.

Anything the hook cannot read also asks: it never fails open.
"""

import json
import re
import sys

QUOTING = re.compile(r"[\"'\\]")
CARD = re.compile(r"\bcard\b")
APPLY = re.compile(r"\bapply\b")
OTHER_ROUTES = re.compile(r"ws\.card|from\s+ws\s+import\s+card|run_apply")
WS = re.compile(r"\bws\b")
EXPANSION = re.compile(r"[${`]|\b(?:eval|base64|xxd|printf)\b")
LINE_CONTINUATION = re.compile(r"\\\r?\n")

REASON = (
    "This command may apply a card approval (ws card apply --approve): it writes to Jira. "
    "Your yes in this prompt is the approval."
)


def applies_an_approval(command: str) -> bool:
    plain = QUOTING.sub("", command)
    if CARD.search(plain) and APPLY.search(plain):
        return True
    if OTHER_ROUTES.search(plain):
        return True
    names_ws = WS.search(plain) or CARD.search(plain)
    return bool(names_ws and (EXPANSION.search(plain) or LINE_CONTINUATION.search(command)))


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
