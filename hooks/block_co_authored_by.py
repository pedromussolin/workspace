"""Claude Code PreToolUse gate: blocks `git commit` commands that add a Co-Authored-By trailer.

Exit 2 blocks the tool call and sends stderr back to Claude. Any internal error also exits 2,
because Claude Code treats other non-zero codes as non-blocking and the gate would fail open.
"""

import json
import re
import sys

GIT_COMMIT = re.compile(r"\bgit\b.*\bcommit\b", re.DOTALL)
TRAILER = re.compile(r"co-authored-by", re.IGNORECASE)


def main() -> int:
    try:
        payload = json.load(sys.stdin)
        command = payload.get("tool_input", {}).get("command", "")
        if not isinstance(command, str):
            raise TypeError("tool_input.command is not a string")
    except Exception as error:
        print(f"Co-Authored-By gate could not read the tool input ({error}); blocking.", file=sys.stderr)
        return 2
    if GIT_COMMIT.search(command) and TRAILER.search(command):
        print(
            "User rule: commits never carry Co-Authored-By. Run the commit again without that line.",
            file=sys.stderr,
        )
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
