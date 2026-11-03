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
    assert hook["permissionDecisionReason"] == ("Gravar fora — GitHub\nCriar PR")


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
    assert len(lines) == 3


def test_too_many_lines_are_counted():
    lines = decision.ask_text("t", [f"l{n}" for n in range(20)]).splitlines()
    assert len(lines) == decision.MAX_LINES
    assert lines[-1] == "(+18 linhas)"
    assert "aprova" not in "".join(lines)


def test_body_summary():
    assert decision.body_summary("") == "vazio"
    assert decision.body_summary("\nolá\n") == '1 linha (primeira: "olá")'
    assert decision.body_summary("a\nb\nc") == '3 linhas (primeira: "a")'


def test_warning_lines_go_right_after_the_title_in_order():
    text = decision.ask_text("t", ["a", "ATENÇÃO: um", "b", "ATENÇÃO: dois"])
    assert text.splitlines() == ["t", "ATENÇÃO: um", "ATENÇÃO: dois", "(+2 linhas)"]
    shown = decision.ask_text("t", ["a", "ATENÇÃO: um", "b"]).splitlines()
    assert shown == ["t", "ATENÇÃO: um", "a", "b"]


def test_warning_lines_are_never_folded_nor_cut():
    long_warning = "ATENÇÃO: " + "x" * 300
    lines = decision.ask_text("t", [f"l{n}" for n in range(20)] + ["ATENÇÃO: fim", long_warning])
    shown = lines.splitlines()
    assert shown[1:3] == ["ATENÇÃO: fim", long_warning]
    assert shown[-1] == "(+20 linhas)"


def test_warnings_beyond_the_room_all_stay():
    warnings = [f"ATENÇÃO: {n}" for n in range(12)]
    shown = decision.ask_text("t", ["a", *warnings, "b"]).splitlines()
    assert shown[1:13] == warnings
    assert shown[13:] == ["(+2 linhas)"]


def test_the_box_has_no_footer_and_a_short_title():
    text = decision.ask_text("x" * 100, ["a"])
    assert "aprova" not in text
    assert len(text.splitlines()[0]) == decision.TITLE_WIDTH


def test_trigger_is_short_and_in_backticks():
    assert decision.trigger("git push") == "`git push`"
    assert len(decision.trigger("x" * 200)) == decision.TRIGGER_WIDTH + 2
    assert decision.trigger("a`b") == "`a'b`"


def test_control_and_format_characters_become_visible():
    text = decision.ask_text("t\u202etítulo", ["a\x1b[31mb", "x\u200by", "\u202e"])
    assert text.splitlines() == ["t�título", "a�[31mb", "x�y", "�"]


def test_cut_replaces_control_characters():
    assert decision.cut("a\u202eb\ufeffc\x00d") == "a�b�c�d"


def test_equal_lines_show_once():
    assert decision.ask_text("t", ["a", "ATENÇÃO: x", "a", "ATENÇÃO: x"]).splitlines() == [
        "t",
        "ATENÇÃO: x",
        "a",
    ]
