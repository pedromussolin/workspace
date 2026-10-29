"""Claude Code PreToolUse gate: nothing is written outside the machine without a PT-BR approval box.

Registered with the matcher `Bash|mcp__.*`. `Bash` goes to `gate.bash_rules`, every `mcp__*` tool
to `gate.mcp_rules`, anything else passes. The decision is printed as the hook's JSON: nothing
for `pass` (the normal permission flow goes on), `ask` (Claude Code shows the box) or `deny`.

It never fails open: any error, a rules module that is missing included, answers `ask`, and the
exit code is always 0, because Claude Code treats any other code but 2 as "go ahead". A hook that
times out also lets the call run, so a hard deadline (`DEADLINE_SECONDS`) answers `ask` too.

The `gate` package is loaded from this file's folder under the name `workspace_gate`, and the
folder never goes on `sys.path`: a `json.py` or `tomllib.py` planted next to the hooks must not
shadow the standard library, and another `gate` on the path must not stand in for ours.
"""

import importlib
import importlib.util
import json
import os
import signal
import sys
from pathlib import Path

PACKAGE = "workspace_gate"

FAILURE_TITLE = "Não consegui ler esta chamada"
FAILURE_ADVICE = "Confira o comando antes de aprovar."
LATE_TITLE = "Não consegui ler esta chamada a tempo"
DEADLINE_SECONDS = 5.0


def gate(module: str):
    """A module of the `gate` package next to this file."""
    if PACKAGE not in sys.modules:
        folder = Path(__file__).resolve().parent / "gate"
        spec = importlib.util.spec_from_file_location(
            PACKAGE, folder / "__init__.py", submodule_search_locations=[str(folder)]
        )
        if spec is None or spec.loader is None:
            raise ImportError(f"no gate package in {folder}")
        package = importlib.util.module_from_spec(spec)
        sys.modules[PACKAGE] = package
        try:
            spec.loader.exec_module(package)
        except BaseException:
            del sys.modules[PACKAGE]
            raise
    return importlib.import_module(f"{PACKAGE}.{module}")


def route(payload: dict) -> str | None:
    """The hook's stdout for this call; None means print nothing."""
    decision = gate("decision")

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
        return decision.to_output(gate("bash_rules").decide(command, cwd))
    if isinstance(name, str) and name.startswith("mcp__"):
        if not isinstance(tool_input, dict):
            raise TypeError("tool_input is not an object")
        return decision.to_output(gate("mcp_rules").decide(name, tool_input, cwd))
    return None


def failure(error: Exception) -> str:
    lines = [f"Erro: {type(error).__name__}: {error}", FAILURE_ADVICE]
    try:
        decision = gate("decision")
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
