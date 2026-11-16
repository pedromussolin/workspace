"""The /card skill may be started by the model; its writes stay behind the approval box."""

from pathlib import Path

from ws import bootstrap

SKILL = Path(__file__).resolve().parents[1] / "skills" / "card" / "SKILL.md"


def _front_matter() -> str:
    text = SKILL.read_text(encoding="utf-8")
    assert text.startswith("---\n")
    return text.split("\n---\n", 1)[0]


def test_card_skill_can_be_started_by_the_model():
    assert "disable-model-invocation" not in _front_matter()


def test_card_skill_says_every_write_waits_for_the_box():
    assert "approval box" in _front_matter()
    assert "never answers the approval box" in SKILL.read_text(encoding="utf-8")


def test_card_apply_keeps_its_ask_rule():
    assert bootstrap.CARD_ASK_RULE == "Bash(ws card apply:*)"
