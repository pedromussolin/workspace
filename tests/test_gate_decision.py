import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "hooks"))

from gate import decision  # noqa: E402


def test_pass_prints_nothing():
    assert decision.to_output(decision.PASS) is None


def test_ask_output_carries_the_text():
    output = json.loads(decision.to_output(decision.ask("Gravar fora — GitHub", ["Criar PR"])))
    hook = output["hookSpecificOutput"]
    assert hook["permissionDecision"] == "ask"
    assert hook["permissionDecisionReason"] == (
        'Gravar fora — GitHub\nCriar PR\n"Yes" aprova só esta chamada.'
    )


def test_deny_output():
    hook = json.loads(decision.to_output(decision.deny("found a secret")))["hookSpecificOutput"]
    assert hook == {
        "hookEventName": "PreToolUse",
        "permissionDecision": "deny",
        "permissionDecisionReason": "found a secret",
    }


def test_lines_are_flattened_and_cut():
    text = decision.ask_text("t", ["a\n  b", "x" * 300, "  "])
    lines = text.splitlines()
    assert lines[1] == "a b"
    assert len(lines[2]) == decision.MAX_WIDTH and lines[2].endswith("…")
    assert len(lines) == 4


def test_too_many_lines_are_counted():
    lines = decision.ask_text("t", [f"l{n}" for n in range(20)]).splitlines()
    assert len(lines) == decision.MAX_LINES
    assert lines[-2] == "(+13 linhas)"
    assert lines[-1] == decision.FOOTER


def test_body_summary():
    assert decision.body_summary("") == "vazio"
    assert decision.body_summary("\nolá\n") == '1 linha (primeira: "olá")'
    assert decision.body_summary("a\nb\nc") == '3 linhas (primeira: "a")'
