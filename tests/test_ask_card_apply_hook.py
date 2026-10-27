import json
import subprocess
import sys
from pathlib import Path

import pytest

HOOK = Path(__file__).resolve().parents[1] / "hooks" / "ask_card_apply.py"


def run_hook(stdin: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(HOOK)], input=stdin, capture_output=True, text=True, check=False
    )


def run_command(command: object) -> subprocess.CompletedProcess[str]:
    return run_hook(json.dumps({"tool_input": {"command": command}}))


def decision(result: subprocess.CompletedProcess[str]) -> dict:
    assert result.returncode == 0, result.stderr
    return json.loads(result.stdout)["hookSpecificOutput"]


@pytest.mark.parametrize(
    "command",
    [
        "ws card apply ~/.local/share/workspace/cards/drafts --approve abcdef012345",
        "ws card apply drafts --approve=abcdef012345",
        "uv run ws card apply drafts --approve abcdef012345",
        "uv run --project /srv/ws ws card apply d.md --approve abcdef012345",
        "/srv/ws/.venv/bin/ws card apply d.md --approve abcdef012345",
        "python3 -m ws card apply d.md --approve abcdef012345",
        "python -m ws.card apply d.md --approve abcdef012345",
        "bash -c 'ws card apply d.md --approve abcdef012345'",
        'sh -c "uv run ws card apply d.md --approve abcdef012345"',
        "cd /srv/ws && ws card apply d.md --approve abcdef012345",
        "ws card   apply d.md   --approve abcdef012345",
        "ws  card\tapply d.md --approve abcdef012345",
        "ws card apply d.md --appr''ove abcdef012345",
        'ws card apply d.md --"approve" abcdef012345',
        "ws card apply d.md --appro\\ve abcdef012345",
        "WS_X=1 ws card apply d.md --approve abcdef012345",
        'python3 -c \'import ws.card; ws.card.run_apply("d.md", None, "abcdef012345")\' --approve',
        "echo ok; ws card apply d.md --approve abcdef012345; echo done",
    ],
)
def test_any_way_of_applying_an_approval_asks(command):
    result = decision(run_command(command))

    assert result["hookEventName"] == "PreToolUse"
    assert result["permissionDecision"] == "ask"
    assert "card" in result["permissionDecisionReason"]


@pytest.mark.parametrize(
    "command",
    [
        "ws card preview d.md",
        "ws card check d.md",
        "ws card epics",
        "ws card apply d.md",
        "git commit -m 'feat: x'",
        "grep -rn approve src",
        "uv run pytest -q",
        "ws task list --approve",
        "",
    ],
)
def test_other_commands_pass_without_a_decision(command):
    result = run_command(command)

    assert result.returncode == 0
    assert result.stdout == ""


def test_a_payload_without_a_command_passes():
    result = run_hook(json.dumps({"tool_input": {}}))

    assert (result.returncode, result.stdout) == (0, "")


@pytest.mark.parametrize(
    "stdin", ["not json", "[]", "", json.dumps({"tool_input": {"command": 3}})]
)
def test_an_unreadable_payload_asks_instead_of_failing_open(stdin):
    result = decision(run_hook(stdin))

    assert result["permissionDecision"] == "ask"
    assert "could not" in result["permissionDecisionReason"]
