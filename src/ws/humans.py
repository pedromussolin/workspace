"""Whether ws runs under a person's hands: the test that lets `ws card apply` and `ws setup` ask
for an approval on the terminal instead of the Claude Code gate."""

import os
import re
import sys
from pathlib import Path, PurePath

PROC = Path("/proc")
AGENT_HARNESSES = frozenset(
    {"claude", "claude-code", "opencode", "codex", "aider", "gemini", "cursor-agent", "goose"}
)
AGENT_INTERPRETERS = frozenset({"node", "nodejs", "bun", "deno"})


def _agent_names(words: list[str], comm: str) -> bool:
    """Whether a process is an agent harness: its name, its command, or (run by an interpreter,
    such as `node .../codex.js`) any word of its command line."""
    first = PurePath(words[0]).name if words else ""
    candidates = [comm, first]
    if first in AGENT_INTERPRETERS or re.fullmatch(r"python[0-9.]*", first):
        for word in words[1:]:
            path = PurePath(word)
            candidates += [path.name, path.parent.name]
    return any(
        name in AGENT_HARNESSES or PurePath(name).stem in AGENT_HARNESSES for name in candidates
    )


def under_agent_harness() -> bool:
    """Whether an ancestor process is an agent harness. Anything unreadable counts as yes."""
    pid, seen = os.getpid(), set()
    while pid > 1 and pid not in seen:
        seen.add(pid)
        try:
            stat_text = (PROC / str(pid) / "stat").read_text(encoding="utf-8", errors="replace")
            comm = (PROC / str(pid) / "comm").read_text(encoding="utf-8", errors="replace")
            cmdline = (PROC / str(pid) / "cmdline").read_bytes()
            fields = stat_text[stat_text.rindex(")") + 1 :].split()
            parent = int(fields[1])
        except (OSError, ValueError, IndexError):
            return True
        words = cmdline.decode("utf-8", errors="replace").split("\0")
        if _agent_names([word for word in words if word], comm.strip()):
            return True
        pid = parent
    return False


def by_hand() -> bool:
    """A person at a real terminal: both streams are TTYs, `CLAUDECODE` is not set and no ancestor
    process is an agent harness (`env -u CLAUDECODE script -qec ...` run by the model has a pseudo
    terminal but still descends from the harness).

    Limit: a process that detaches and is reparented to init (a double fork) leaves no ancestor to
    see and escapes the walk. The approval gate does not close it either: it asks for `setsid` and
    `nohup` only when the program they start is one it watches (`ws`, `git`, `gh`, `curl`, `wget`),
    so a double fork of any other program passes. Phase 3 (the sandbox) closes it."""
    return (
        sys.stdin.isatty()
        and sys.stdout.isatty()
        and "CLAUDECODE" not in os.environ
        and not under_agent_harness()
    )
