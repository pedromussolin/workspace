import json
import shutil
import subprocess
import sys
from pathlib import Path

HOOKS = Path(__file__).resolve().parents[1] / "hooks"
SHIM = HOOKS / "ask_card_apply.py"


def run(shim: Path, command: str) -> subprocess.CompletedProcess[str]:
    payload = {"tool_name": "Bash", "tool_input": {"command": command}, "cwd": "/srv"}
    return subprocess.run(
        [sys.executable, "-I", str(shim)],
        input=json.dumps(payload),
        capture_output=True,
        text=True,
        check=False,
    )


def test_the_old_path_runs_the_gate(tmp_path, monkeypatch):
    monkeypatch.setenv("WS_DATA_DIR", str(tmp_path))
    (tmp_path / "cards" / "pending").mkdir(parents=True)
    (tmp_path / "cards" / "pending" / "abcdef012345.json").write_text(
        json.dumps({"summary": ["TS-1: mover"]}), encoding="utf-8"
    )
    result = run(SHIM, "ws card apply d.md --approve abcdef012345")
    assert result.returncode == 0
    hook = json.loads(result.stdout)["hookSpecificOutput"]
    assert hook["permissionDecision"] == "ask"
    assert "Jira" in hook["permissionDecisionReason"]


def test_a_harmless_command_passes():
    result = run(SHIM, "git status")
    assert result.returncode == 0
    assert result.stdout == ""


def test_a_missing_gate_asks(tmp_path):
    shim = tmp_path / "ask_card_apply.py"
    shutil.copy(SHIM, shim)
    result = run(shim, "git status")
    assert result.returncode == 0
    hook = json.loads(result.stdout)["hookSpecificOutput"]
    assert hook["permissionDecision"] == "ask"
    assert "portão de aprovação" in hook["permissionDecisionReason"]
