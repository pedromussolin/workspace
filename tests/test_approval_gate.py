"""The approval gate's entry point: routing, silence for the rest, and never failing open."""

import json
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

HOOKS = Path(__file__).resolve().parents[1] / "hooks"
FAILURE_TITLE = "Não consegui ler esta chamada"
FOOTER = '"Yes" aprova só esta chamada.'


@pytest.fixture
def hooks_copy(tmp_path):
    """A private copy of the hooks folder that a test can break or stub."""
    target = tmp_path / "hooks"
    shutil.copytree(HOOKS, target, ignore=shutil.ignore_patterns("__pycache__"))
    return target


def run_raw(stdin, hooks=HOOKS):
    return subprocess.run(
        [sys.executable, "-I", str(hooks / "approval_gate.py")],
        input=stdin,
        capture_output=True,
        text=True,
        cwd="/",
        check=False,
    )


def run(payload, hooks=HOOKS):
    return run_raw(json.dumps(payload), hooks)


def decision_of(result):
    assert result.returncode == 0, result.stderr
    return json.loads(result.stdout)["hookSpecificOutput"]


def bash(command, cwd="/work"):
    return {"tool_name": "Bash", "tool_input": {"command": command}, "cwd": cwd}


def stub(hooks, module, body):
    (hooks / "gate" / f"{module}.py").write_text(body, encoding="utf-8")


def test_a_bash_call_goes_to_the_bash_rules(tmp_path):
    result = run(bash("git push origin feature/x", cwd="/srv/repo"))
    decision = decision_of(result)

    assert decision["hookEventName"] == "PreToolUse"
    assert decision["permissionDecision"] == "ask"
    assert decision["permissionDecisionReason"].splitlines()[0] == "Gravar fora — GitHub"
    assert "/srv/repo" in decision["permissionDecisionReason"]
    assert decision["permissionDecisionReason"].endswith(FOOTER)


def test_a_bash_call_the_rules_pass_prints_nothing():
    result = run(bash("ls -la"))

    assert (result.returncode, result.stdout, result.stderr) == (0, "", "")


def test_the_bash_rules_get_the_command_and_the_cwd(hooks_copy):
    stub(
        hooks_copy,
        "bash_rules",
        "from .decision import ask\n"
        "def decide(command, cwd):\n"
        "    return ask('stub', [repr(command), repr(cwd)])\n",
    )
    reason = decision_of(run(bash("echo hi", cwd="/some/dir"), hooks_copy))[
        "permissionDecisionReason"
    ]

    assert reason.splitlines()[1:3] == ["'echo hi'", "'/some/dir'"]


def test_a_missing_cwd_reaches_the_rules_as_an_empty_string(hooks_copy):
    stub(
        hooks_copy,
        "bash_rules",
        "from .decision import ask\n"
        "def decide(command, cwd):\n"
        "    return ask('stub', [repr(cwd)])\n",
    )
    payload = {"tool_name": "Bash", "tool_input": {"command": "x"}}
    reason = decision_of(run(payload, hooks_copy))["permissionDecisionReason"]

    assert reason.splitlines()[1] == "''"


def test_an_mcp_call_goes_to_the_mcp_rules(hooks_copy):
    stub(
        hooks_copy,
        "mcp_rules",
        "import json\n"
        "from .decision import ask\n"
        "def decide(tool_name, tool_input, cwd):\n"
        "    return ask('stub', [tool_name, json.dumps(tool_input, sort_keys=True), cwd])\n",
    )
    payload = {
        "tool_name": "mcp__github__create_pull_request",
        "tool_input": {"title": "x", "base": "main"},
        "cwd": "/srv/repo",
    }
    lines = decision_of(run(payload, hooks_copy))["permissionDecisionReason"].splitlines()

    assert lines[0] == "stub"
    assert lines[1:4] == [
        "mcp__github__create_pull_request",
        '{"base": "main", "title": "x"}',
        "/srv/repo",
    ]


def test_a_decision_of_the_mcp_rules_can_be_a_deny(hooks_copy):
    stub(
        hooks_copy,
        "mcp_rules",
        "from .decision import deny\n"
        "def decide(tool_name, tool_input, cwd):\n"
        "    return deny('achado')\n",
    )
    decision = decision_of(
        run({"tool_name": "mcp__x__y", "tool_input": {}, "cwd": "/"}, hooks_copy)
    )

    assert decision["permissionDecision"] == "deny"
    assert decision["permissionDecisionReason"] == "achado"


def test_an_mcp_call_asks_while_the_mcp_rules_are_absent(hooks_copy):
    (hooks_copy / "gate" / "mcp_rules.py").unlink(missing_ok=True)
    decision = decision_of(run({"tool_name": "mcp__x__write", "tool_input": {}}, hooks_copy))

    assert decision["permissionDecision"] == "ask"
    lines = decision["permissionDecisionReason"].splitlines()
    assert lines[0] == FAILURE_TITLE
    assert "mcp_rules" in lines[1]
    assert decision["permissionDecisionReason"].endswith(FOOTER)


@pytest.mark.parametrize(
    "tool_name",
    [
        "Read",
        "Edit",
        "Write",
        "Glob",
        "Grep",
        "WebFetch",
        "Task",
        "Skill",
        "NotebookEdit",
        "",
        None,
    ],
)
def test_other_tools_pass(tool_name):
    result = run({"tool_name": tool_name, "tool_input": {"command": "git push"}, "cwd": "/"})

    assert (result.returncode, result.stdout) == (0, "")


def test_a_payload_without_a_tool_name_passes():
    result = run({"tool_input": {"command": "git push"}})

    assert (result.returncode, result.stdout) == (0, "")


@pytest.mark.parametrize("name", ["bash", "BASH", "mcp_x", "xmcp__x"])
def test_names_that_are_not_exactly_bash_or_mcp_pass(name):
    result = run({"tool_name": name, "tool_input": {"command": "git push"}})

    assert (result.returncode, result.stdout) == (0, "")


@pytest.mark.parametrize("tool_input", [{}, {"command": ""}, {"command": None}, None])
def test_a_bash_call_without_a_command_passes(tool_input):
    result = run({"tool_name": "Bash", "tool_input": tool_input})

    assert (result.returncode, result.stdout) == (0, "")


@pytest.mark.parametrize(
    "stdin",
    [
        "not json",
        "",
        "[]",
        "3",
        '"text"',
        "null",
        '{"tool_name": "Bash", "tool_input": {"command": 3}}',
        '{"tool_name": "Bash", "tool_input": {"command": ["git", "push"]}}',
        '{"tool_name": "Bash", "tool_input": "git push"}',
        '{"tool_name": "Bash", "tool_input": []}',
        '{"tool_name": "mcp__x__y", "tool_input": "text"}',
        '{"tool_name": "mcp__x__y"}',
        '{"tool_name": "mcp__x__y", "tool_input": null}',
    ],
)
def test_a_payload_that_cannot_be_read_asks_and_exits_zero(stdin):
    result = run_raw(stdin)
    decision = decision_of(result)

    assert decision["permissionDecision"] == "ask"
    lines = decision["permissionDecisionReason"].splitlines()
    assert lines[0] == FAILURE_TITLE
    assert lines[1].startswith("Erro: ")
    assert "Confira o comando antes de aprovar." in lines


@pytest.mark.parametrize("locale", ["C", "C.UTF-8", "pt_BR.ISO-8859-1"])
def test_invalid_utf8_and_any_locale_still_give_a_valid_answer(locale, tmp_path):
    result = subprocess.run(
        [sys.executable, "-I", str(HOOKS / "approval_gate.py")],
        input=b'{"tool_name": "Bash", "tool_input": {"command": "git push \xff\xfe \xc3\xa3"}}',
        capture_output=True,
        env={"PATH": "/usr/bin:/bin", "LC_ALL": locale, "HOME": str(tmp_path)},
        cwd="/",
        check=False,
    )

    assert result.returncode == 0, result.stderr
    output = json.loads(result.stdout.decode("utf-8"))["hookSpecificOutput"]
    assert output["permissionDecision"] == "ask"
    assert "ã" in output["permissionDecisionReason"]


def test_a_crash_inside_the_rules_asks_and_exits_zero(hooks_copy):
    stub(hooks_copy, "bash_rules", "def decide(command, cwd):\n    raise RuntimeError('boom')\n")
    result = run(bash("git push"), hooks_copy)
    decision = decision_of(result)

    assert decision["permissionDecision"] == "ask"
    assert "RuntimeError: boom" in decision["permissionDecisionReason"]
    assert result.stderr == ""


def test_a_syntax_error_in_the_rules_still_asks(hooks_copy):
    stub(hooks_copy, "bash_rules", "def decide(:\n")
    decision = decision_of(run(bash("git push"), hooks_copy))

    assert decision["permissionDecision"] == "ask"
    assert "SyntaxError" in decision["permissionDecisionReason"]


def test_a_missing_gate_package_still_asks_with_a_plain_message(hooks_copy):
    shutil.rmtree(hooks_copy / "gate")
    decision = decision_of(run(bash("git push"), hooks_copy))

    assert decision["permissionDecision"] == "ask"
    assert decision["permissionDecisionReason"].startswith(FAILURE_TITLE)


def test_the_hook_works_from_any_cwd_under_isolated_mode(tmp_path):
    result = subprocess.run(
        [sys.executable, "-I", str(HOOKS / "approval_gate.py")],
        input=json.dumps(bash("git push", cwd=str(tmp_path))),
        capture_output=True,
        text=True,
        cwd=tmp_path,
        check=False,
    )

    assert decision_of(result)["permissionDecision"] == "ask"


def test_exit_code_is_zero_for_every_kind_of_answer(hooks_copy):
    for payload in (
        bash("ls"),
        bash("git push"),
        {"tool_name": "Read"},
        {"tool_name": "mcp__x__y"},
    ):
        assert run(payload, hooks_copy).returncode == 0
    assert run_raw("garbage", hooks_copy).returncode == 0


def test_a_huge_command_is_answered(tmp_path):
    command = "echo " + "a" * 200_000 + "\n" + "git push\n" * 200
    result = run(bash(command))

    assert decision_of(result)["permissionDecision"] == "ask"
