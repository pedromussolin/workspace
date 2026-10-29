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


def test_warning_lines_go_right_after_the_title_in_order():
    text = decision.ask_text("t", ["a", "ATENÇÃO: um", "b", "ATENÇÃO: dois"])
    assert text.splitlines() == ["t", "ATENÇÃO: um", "ATENÇÃO: dois", "a", "b", decision.FOOTER]


def test_warning_lines_are_never_folded_nor_cut():
    long_warning = "ATENÇÃO: " + "x" * 300
    lines = decision.ask_text("t", [f"l{n}" for n in range(20)] + ["ATENÇÃO: fim", long_warning])
    shown = lines.splitlines()
    assert shown[1:3] == ["ATENÇÃO: fim", long_warning]
    assert len(shown) == decision.MAX_LINES
    assert shown[-2] == "(+15 linhas)"


def test_warnings_beyond_the_room_all_stay():
    warnings = [f"ATENÇÃO: {n}" for n in range(12)]
    shown = decision.ask_text("t", ["a", *warnings, "b"]).splitlines()
    assert shown[1:13] == warnings
    assert shown[13:] == ["(+2 linhas)", decision.FOOTER]


def test_control_and_format_characters_become_visible():
    text = decision.ask_text(
        "t\u202etítulo", ["a\x1b[31mb", "x\u200by", "\u202e", "tab\tok", "bell\x07"]
    )
    assert text.splitlines() == [
        "t�título",
        "a�[31mb",
        "x�y",
        "�",
        "tab ok",
        "bell�",
        decision.FOOTER,
    ]


def test_cut_replaces_control_characters():
    assert decision.cut("a\u202eb\ufeffc\x00d") == "a�b�c�d"
