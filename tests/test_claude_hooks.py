import json
import shlex
import subprocess
import sys
from pathlib import Path

HOOK = Path(__file__).resolve().parents[1] / "hooks" / "block_co_authored_by.py"


def run_hook(stdin: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(HOOK)], input=stdin, capture_output=True, text=True, check=False
    )


def run_command(command: object) -> subprocess.CompletedProcess[str]:
    return run_hook(json.dumps({"tool_input": {"command": command}}))


def test_commit_with_the_trailer_is_blocked():
    message = "fix: x\n\nCo-Authored-By: Someone <someone@example.com>"
    result = run_command(f'git commit -m "{message}"')
    assert result.returncode == 2
    assert "never carry" in result.stderr


def test_trailer_check_ignores_case():
    assert run_command("git commit -m 'x' -m 'CO-AUTHORED-BY: a'").returncode == 2


def test_commit_with_the_trailer_in_a_heredoc_is_blocked():
    command = "git commit -m \"$(cat <<'EOF'\nfix: x\n\nCo-Authored-By: a\nEOF\n)\""
    assert run_command(command).returncode == 2


def test_commit_without_the_trailer_passes():
    assert run_command('git commit -m "fix: x"').returncode == 0


def test_grep_for_the_trailer_passes():
    assert run_command("grep -rn 'Co-Authored-By' .").returncode == 0


def test_payload_without_a_command_passes():
    assert run_hook(json.dumps({"tool_input": {}})).returncode == 0


def test_invalid_json_blocks():
    result = run_hook("not json")
    assert result.returncode == 2
    assert "blocking" in result.stderr


def test_non_string_command_blocks():
    assert run_command(["git", "commit"]).returncode == 2
    assert run_command(None).returncode == 2


def test_payload_that_is_not_an_object_blocks():
    assert run_hook("[]").returncode == 2
    assert run_hook("").returncode == 2


def test_the_protected_copy_runs_the_hook_with_isolated_python(tmp_path):
    from ws.bootstrap import run_setup

    repo = tmp_path / "repo"
    (repo / "hooks").mkdir(parents=True)
    (repo / "hooks" / HOOK.name).write_bytes(HOOK.read_bytes())
    copy = tmp_path / "claude" / "hooks" / "workspace"
    run_setup(
        repo, tmp_path / "config", tmp_path / "skills", tmp_path / "settings.json", hooks_dir=copy
    )

    trailer = "Co-Authored-" + "By: a"
    payload = json.dumps({"tool_input": {"command": f"git commit -m 'x' -m '{trailer}'"}})
    from ws.bootstrap import _hook_command

    command = shlex.split(_hook_command(copy, HOOK.name))
    assert command[1:3] == ["-I", "-B"]
    result = subprocess.run(
        [sys.executable, *command[1:]], input=payload, capture_output=True, text=True
    )
    assert result.returncode == 2
    assert not list(copy.rglob("__pycache__"))
