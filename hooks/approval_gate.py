"""Claude Code PreToolUse gate: nothing is written outside the machine without a PT-BR approval box.

Registered with the matcher `Bash|mcp__.*`. `Bash` goes to `gate.bash_rules`, every `mcp__*` tool
to `gate.mcp_rules`, anything else passes. The decision is printed as the hook's JSON: nothing
for `pass` (the normal permission flow goes on), `ask` (Claude Code shows the box) or `deny`.

It never fails open: any error, a rules module that is missing included, answers `ask`, and the
exit code is always 0, because Claude Code treats any other code but 2 as "go ahead". A hook that
times out also lets the call run, so a hard deadline (`DEADLINE_SECONDS`) answers `ask` too.
"""

import json
import os
import signal
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

FAILURE_TITLE = "Não consegui ler esta chamada"
FAILURE_ADVICE = "Confira o comando antes de aprovar."
LATE_TITLE = "Não consegui ler esta chamada a tempo"
DEADLINE_SECONDS = 5.0


def route(payload: dict) -> str | None:
    """The hook's stdout for this call; None means print nothing."""
    from gate import decision

    name = payload.get("tool_name")
    tool_input = payload.get("tool_input")
    cwd = str(payload.get("cwd") or "")
    if name == "Bash":
        if tool_input is not None and not isinstance(tool_input, dict):
            raise TypeError("tool_input is not an object")
        command = (tool_input or {}).get("command")
        if command is None or command == "":
            return None
        if not isinstance(command, str):
            raise TypeError("tool_input.command is not a string")
        from gate import bash_rules

        return decision.to_output(bash_rules.decide(command, cwd))
    if isinstance(name, str) and name.startswith("mcp__"):
        if not isinstance(tool_input, dict):
            raise TypeError("tool_input is not an object")
        from gate import mcp_rules

        return decision.to_output(mcp_rules.decide(name, tool_input, cwd))
    return None


def failure(error: Exception) -> str:
    lines = [f"Erro: {type(error).__name__}: {error}", FAILURE_ADVICE]
    try:
        from gate import decision

        output = decision.to_output(decision.ask(FAILURE_TITLE, lines))
        if output is not None:
            return output
    except Exception:
        pass
    return _ask_json("\n".join([FAILURE_TITLE, *lines]))


def _ask_json(reason: str) -> str:
    return json.dumps(
        {
            "hookSpecificOutput": {
                "hookEventName": "PreToolUse",
                "permissionDecision": "ask",
                "permissionDecisionReason": reason,
            }
        },
        ensure_ascii=False,
    )


def _late(signum, frame) -> None:
    """Out of time: answer `ask` and leave at once, whatever the rules were doing."""
    reason = "\n".join([LATE_TITLE, FAILURE_ADVICE, '"Yes" aprova só esta chamada.'])
    os.write(1, _ask_json(reason).encode("utf-8") + b"\n")
    os._exit(0)


def main() -> int:
    if hasattr(signal, "setitimer"):
        signal.signal(signal.SIGALRM, _late)
        signal.setitimer(signal.ITIMER_REAL, DEADLINE_SECONDS)
    try:
        raw = sys.stdin.buffer.read().decode("utf-8", errors="replace")
        output = route(json.loads(raw))
    except Exception as error:
        output = failure(error)
    if hasattr(signal, "setitimer"):
        signal.setitimer(signal.ITIMER_REAL, 0)
    if output is not None:
        # Bytes, not print(): a stdout locale that cannot encode the text must not crash the hook.
        sys.stdout.buffer.write(output.encode("utf-8", errors="replace") + b"\n")
        sys.stdout.buffer.flush()
    return 0


if __name__ == "__main__":
    sys.exit(main())
