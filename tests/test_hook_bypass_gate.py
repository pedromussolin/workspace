import json
import shutil
import subprocess
import sys
import time
from pathlib import Path

import pytest

HOOK = Path(__file__).resolve().parents[1] / "hooks" / "block_hook_bypass.py"

HEREDOC_MESSAGE = """git commit -m "$(cat <<'EOF'
docs: explicar o gate

Nunca git commit --no-verify; don't pular o hook.
EOF
)\""""

HEREDOC_TO_FILE = """cat > notes.md <<'EOF'
Never run git commit --no-verify, don't.
EOF"""


def run_hook(stdin: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(HOOK)], input=stdin, capture_output=True, text=True, check=False
    )


def run_command(command: object) -> subprocess.CompletedProcess[str]:
    return run_hook(json.dumps({"tool_input": {"command": command}}))


@pytest.mark.parametrize(
    "command",
    [
        "git commit --no-verify -m x",
        "git commit -m x --no-verify",
        "git commit --no-ver -m x",
        "git push --no-verify",
        "git push origin main --no-verify",
        "git merge --no-verify feat/x",
        "git cherry-pick --no-verify abc123",
        "git revert --no-verify HEAD",
        "git rebase --no-verify main",
        "git pull --no-verify",
        "git commit -n -m x",
        "git commit -nm x",
        "git commit -anm x",
        "git commit -a -n",
        "git -C repo commit --no-verify",
        "/usr/bin/git commit --no-verify",
        "git -c core.hooksPath=/dev/null commit -m x",
        "git -c core.hookspath=/dev/null push",
        "git -C repo -c core.hooksPath=.githooks push",
        "git --config-env=core.hooksPath=HOOKS commit -m x",
        "GIT_CONFIG_COUNT=1 GIT_CONFIG_KEY_0=core.hooksPath GIT_CONFIG_VALUE_0=x git commit",
        "env GIT_CONFIG_PARAMETERS=\"'core.hooksPath=/dev/null'\" git commit -m x",
        "git config core.hooksPath /dev/null",
        "git config --local core.hooksPath .git/hooks",
        "git config --global core.hooksPath hooks",
        "git config core.hooksPath .githooks --global",
        "git config --unset core.hooksPath",
        "git config --unset-all core.hooksPath",
        "git config set core.hooksPath x",
        "git add -A && git commit --no-verify -m x",
        "cd repo; git commit -n",
        "git status || git push --no-verify",
        "ls | git commit -n",
        "git add .\ngit commit --no-verify -m x",
        "git commit \\\n  --no-verify -m x",
        "echo $(git commit --no-verify)",
        'git commit -m "$(git commit --no-verify)"',
        "x=`git commit --no-verify`",
        "bash -c 'git commit --no-verify -m x'",
        'sh -c "git push --no-verify"',
        "bash -lc 'cd repo && git commit -n'",
        "eval git commit --no-verify",
        "env FOO=1 git commit -n",
        "sudo git push --no-verify",
        "timeout 60 git push --no-verify",
        "if git commit --no-verify; then echo done; fi",
        'git commit --no-verify -m "unclosed',
        "echo 'unclosed; git config core.hooksPath /dev/null",
    ],
)
def test_bypass_is_blocked(command):
    result = run_command(command)
    assert result.returncode == 2, command
    assert result.stderr.startswith("Blocked:")


@pytest.mark.parametrize(
    "command",
    [
        'git commit -m "fix: x"',
        "git commit -am x",
        "git commit -mnote",
        "git commit -F msg.txt",
        'git commit -m "docs: never use git commit --no-verify"',
        "git commit -m 'docs: cite `git commit --no-verify` in the text'",
        "git commit -m x -- -n",
        "git commit -m x && git push origin main",
        "git -c user.name=Test commit -m x",
        "git config user.name Test",
        "git status",
        "git log --oneline -n 3",
        "git push -n",
        "git push --dry-run",
        "git merge -n feat/x",
        "git cherry-pick -n abc123",
        "git config core.hooksPath .githooks",
        "git -C /some/repo config core.hooksPath .githooks",
        "git config --get core.hooksPath",
        "git config get core.hooksPath",
        "git config --list",
        "grep -rn -- '--no-verify' .",
        "grep hooksPath README.md",
        'echo "git commit --no-verify"',
        "echo never git commit --no-verify",
        "echo '$(git commit --no-verify)'",
        "uv run pytest -q",
        HEREDOC_MESSAGE,
        HEREDOC_TO_FILE,
        "git config core.hooksPath",
        "git config --global core.hooksPath",
        "git config --show-origin --get-all core.hooksPath",
        "git config --get-regexp 'hooks|alias'",
        "git config alias.st status",
        "git config --global alias.l 'log --oneline'",
        "git config --global alias.sh '!git show'",
        "git config --unset user.name",
        "git config --remove-section alias",
    ],
)
def test_ordinary_commands_pass(command):
    result = run_command(command)
    assert result.returncode == 0, result.stderr
    assert result.stderr == ""


def test_the_message_names_the_reason():
    result = run_command("git -c core.hooksPath=/dev/null commit -m x")
    assert "core.hooksPath override" in result.stderr


def test_unparseable_command_without_the_keywords_passes():
    assert run_command("echo 'unclosed").returncode == 0


def test_payload_without_a_command_passes():
    assert run_hook(json.dumps({"tool_input": {}})).returncode == 0


def test_invalid_json_blocks():
    result = run_hook("not json")
    assert result.returncode == 2
    assert "blocking" in result.stderr


def test_non_string_command_blocks():
    assert run_command(["git", "commit", "--no-verify"]).returncode == 2
    assert run_command(None).returncode == 2


def test_payload_with_a_wrong_shape_blocks():
    assert run_hook("[]").returncode == 2
    assert run_hook("").returncode == 2
    assert run_hook(json.dumps({"tool_input": []})).returncode == 2


def test_it_runs_under_isolated_mode_from_any_folder(tmp_path):
    """Registered as `python3 -I`, which does not put the script's folder on the path."""
    payload = json.dumps({"tool_input": {"command": "git commit --no-verify -m x"}})
    result = subprocess.run(
        [sys.executable, "-I", str(HOOK)],
        input=payload,
        capture_output=True,
        text=True,
        cwd=tmp_path,
        check=False,
    )

    assert result.returncode == 2
    assert "--no-verify" in result.stderr


def test_it_blocks_when_the_shared_parser_is_missing(tmp_path):
    """Failing to import must not turn into a crash, which Claude Code reads as "go ahead"."""
    copy = tmp_path / "hooks"
    copy.mkdir()
    shutil.copy(HOOK, copy / HOOK.name)
    result = subprocess.run(
        [sys.executable, "-I", str(copy / HOOK.name)],
        input=json.dumps({"tool_input": {"command": "ls"}}),
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 2
    assert "could not load its parser" in result.stderr


def test_deeply_nested_substitutions_are_checked_fast():
    started = time.monotonic()
    result = run_command("echo " + "$(" * 30 + "date" + ")" * 30)

    assert time.monotonic() - started < 3
    assert result.returncode == 0


@pytest.mark.parametrize(
    "command",
    [
        "env -u CLAUDECODE git commit --no-verify",
        "timeout -s KILL 10 git commit -n",
        "stdbuf -oL git push --no-verify",
        "flock /tmp/l git commit --no-verify",
        "ionice -c 3 git commit -n",
        'script -qec "git commit --no-verify" /dev/null',
        'env -S "git commit --no-verify"',
        "watch -n 60 git push --no-verify",
    ],
)
def test_wrappers_with_values_do_not_hide_a_bypass(command):
    assert run_command(command).returncode == 2


@pytest.mark.parametrize(
    "command",
    [
        'git -c alias.c="commit --no-verify" c',
        "git -c alias.c='commit -n' c -m x",
        "git -c alias.c='commit -anm x' c",
        "git -c 'alias.c=!git commit --no-verify' c",
        "git -c 'alias.c=-c core.hooksPath=/dev/null commit' c",
        "git -c alias.h='config core.hooksPath /dev/null' h",
        "git -c alias.p='push --no-ver' p",
    ],
)
def test_an_alias_given_with_dash_c_that_skips_the_hooks_is_blocked(command):
    result = run_command(command)

    assert result.returncode == 2
    assert "alias" in result.stderr


@pytest.mark.parametrize(
    "command",
    ["git -c alias.st=status st", "git -c alias.c='commit -m x' c", "git -c alias.l='!git log' l"],
)
def test_an_ordinary_alias_given_with_dash_c_passes(command):
    assert run_command(command).returncode == 0


@pytest.mark.parametrize("name", ["dataclasses", "time", "shlex", "re"])
def test_a_module_planted_next_to_the_hook_does_not_shadow_the_standard_library(name, tmp_path):
    copy = tmp_path / "hooks"
    shutil.copytree(HOOK.parent, copy, ignore=shutil.ignore_patterns("__pycache__"))
    for folder in (copy, copy / "gate"):
        (folder / f"{name}.py").write_text("import sys\nsys.exit(0)\n", encoding="utf-8")
    result = subprocess.run(
        [sys.executable, "-I", str(copy / HOOK.name)],
        input=json.dumps({"tool_input": {"command": "git commit --no-verify -m x"}}),
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 2


@pytest.mark.parametrize(
    "command",
    [
        "bash <<'EOF'\ngit commit --no-verify -m x\nEOF",
        "sh <<EOF\ngit commit --no-verify -m x\nEOF",
        "dash <<\\EOF\ngit push --no-verify\nEOF",
        "zsh -s <<-'EOF'\n\tgit commit -n\nEOF",
        "sudo bash <<'EOF'\ngit push --no-verify\nEOF",
        "cd repo && bash <<'EOF'\ngit commit -n\nEOF",
        "bash <<'EOF'\nbash -c 'git commit -n'\nEOF",
        "bash <<'EOF'\nls\ngit add .\ngit commit --no-verify -m x\nEOF",
        "source /dev/stdin <<'EOF'\ngit commit -n\nEOF",
        ". /dev/stdin <<'EOF'\ngit commit -n\nEOF",
        "bash -s <<< 'git commit --no-verify'",
        'bash <<< "git commit -n -m x"',
        "sh <<<'git push --no-verify'",
        "sudo bash <<< 'git commit -n'",
        "eval <<< 'git commit -n'",
        ". /dev/stdin <<< 'git push --no-verify'",
        "cat <<EOF\n$(git commit --no-verify -m x)\nEOF",
        "cat <<EOF\n`git commit -n`\nEOF",
        'echo "<<EOF"\ngit commit --no-verify\nEOF',
    ],
)
def test_a_heredoc_or_here_string_that_a_shell_runs_is_scanned(command):
    result = run_command(command)

    assert result.returncode == 2, command
    assert result.stderr.startswith("Blocked:")


@pytest.mark.parametrize(
    "command",
    [
        "git commit -F- <<'EOF'\ndocs: never git commit --no-verify\nEOF",
        "git commit -F - <<'EOF'\ndocs: never git commit -n\nEOF",
        "cat <<'EOF'\ngit commit --no-verify\nEOF",
        "cat <<'EOF' > notes.md\ngit commit -n\nEOF",
        "cat <<EOF\ngit commit --no-verify, in prose\nEOF",
        "grep -q x <<< 'git commit --no-verify'",
        "cat <<< 'git commit -n'",
        "bash <<< 'echo ok'",
        "bash -s <<'EOF'\nls\nEOF",
        "python3 - <<'EOF'\nprint('git commit --no-verify')\nEOF",
    ],
)
def test_a_heredoc_or_here_string_that_is_data_passes(command):
    result = run_command(command)

    assert result.returncode == 0, result.stderr
    assert result.stderr == ""


@pytest.mark.parametrize(
    "command",
    [
        "X='commit --no-verify' git --config-env=alias.ci=X ci",
        "git --config-env alias.ci=X ci",
        "git --config-env=ALIAS.ci=X ci",
        "git --config-env=include.path=X commit",
        "git --config-env=includeIf.gitdir:/x/.path=X commit",
        "git --config-env=core.hookspath=X commit",
        "GIT_CONFIG_COUNT=1 GIT_CONFIG_KEY_0=alias.ci GIT_CONFIG_VALUE_0='commit -n' git ci",
        "GIT_CONFIG_COUNT=1 GIT_CONFIG_KEY_0=include.path GIT_CONFIG_VALUE_0=/tmp/e.cfg git commit",
        "GIT_CONFIG_COUNT=1 GIT_CONFIG_KEY_0=includeIf.x.path GIT_CONFIG_VALUE_0=y git commit",
        "GIT_CONFIG_COUNT=2 GIT_CONFIG_KEY_0=user.name GIT_CONFIG_VALUE_0=x "
        "GIT_CONFIG_KEY_1=alias.ci GIT_CONFIG_VALUE_1='commit -n' git ci",
        "env GIT_CONFIG_KEY_0=alias.ci GIT_CONFIG_VALUE_0='commit -n' git ci",
        "export GIT_CONFIG_COUNT=1 GIT_CONFIG_KEY_0=alias.ci GIT_CONFIG_VALUE_0=x; git ci",
        "GIT_CONFIG_KEY_0=core.hooksPath; git commit",
        "env GIT_CONFIG_PARAMETERS=\"'alias.ci=commit -n'\" git ci",
        "git -c include.path=/tmp/e.cfg commit",
        "git -c INCLUDE.path=/tmp/e.cfg commit",
        "git -c includeIf.gitdir:/x/.path=/tmp/e.cfg commit",
        "git -C repo -c include.path=e.cfg status",
    ],
)
def test_a_config_whose_value_the_gate_cannot_see_is_blocked(command):
    result = run_command(command)

    assert result.returncode == 2, command
    assert result.stderr.startswith("Blocked:")


@pytest.mark.parametrize(
    "command",
    [
        "GIT_CONFIG_COUNT=1 GIT_CONFIG_KEY_0=user.name GIT_CONFIG_VALUE_0=alias.x git commit",
        "GIT_CONFIG_GLOBAL=/dev/null git status",
        "git --config-env=user.name=NAME commit -m x",
        "NAME=x git --config-env user.email=NAME commit -m x",
        "git -c user.name=include.x commit -m x",
        "echo GIT_CONFIG_KEY_0=alias.ci",
    ],
)
def test_other_config_variables_and_keys_pass(command):
    result = run_command(command)

    assert result.returncode == 0, result.stderr


@pytest.mark.parametrize(
    "command",
    [
        "git config alias.ci 'commit --no-verify'",
        "git config --global alias.ci '!git commit -n'",
        "git config --local alias.p 'push --no-ver'",
        "git config --file /tmp/x.cfg alias.ci 'commit -anm x'",
        "git config -f /tmp/x.cfg alias.ci 'commit -n'",
        "git config --add alias.ci 'commit -n'",
        "git config --replace-all alias.ci 'commit -n'",
        "git config set alias.ci 'commit -n'",
        "git config set --global alias.ci '!git commit --no-verify'",
        "git -C repo config alias.ci 'commit -n'",
        "git config ALIAS.ci 'commit -n'",
        "git config alias.h 'config core.hooksPath /dev/null'",
        "git config include.path /tmp/e.cfg",
        "git config --global includeIf.gitdir:/x/.path /tmp/e.cfg",
    ],
)
def test_writing_an_alias_or_an_include_that_skips_the_hooks_is_blocked(command):
    result = run_command(command)

    assert result.returncode == 2, command
    assert result.stderr.startswith("Blocked:")


def test_the_alias_written_with_git_config_is_named_in_the_message():
    result = run_command("git config alias.ci 'commit --no-verify'")

    assert "alias" in result.stderr


@pytest.mark.parametrize(
    "command",
    [
        "git config --remove-section core",
        "git config --global --remove-section Core",
        "git config --rename-section core x",
        "git config --rename-section x core",
        "git config --remove-sec core",
        "git config remove-section core",
        "git config rename-section core x",
        "git config --unset core.hooksPath",
        "git config --unset-all core.hooksPath",
        "git config --unset-a core.hooksPath",
        "git config --global --unset core.hooksPath",
        "git config unset core.hooksPath",
        "git config -f /tmp/x.cfg core.hooksPath /dev/null",
        "git config --comment why core.hooksPath /dev/null",
    ],
)
def test_removing_or_renaming_the_core_section_is_blocked(command):
    result = run_command(command)

    assert result.returncode == 2, command
    assert result.stderr.startswith("Blocked:")
