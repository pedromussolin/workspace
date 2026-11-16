"""The /release skill may be started by the model; its GitHub writes stay behind the box."""

from pathlib import Path

from ws import bootstrap

SKILL = Path(__file__).resolve().parents[1] / "skills" / "release" / "SKILL.md"


def _front_matter() -> str:
    text = SKILL.read_text(encoding="utf-8")
    assert text.startswith("---\n")
    return text.split("\n---\n", 1)[0]


def test_release_skill_can_be_started_by_the_model():
    assert "disable-model-invocation" not in _front_matter()


def test_release_skill_says_every_write_waits_for_the_box():
    assert "approval box" in _front_matter()
    assert "never\nanswers the approval box" in SKILL.read_text(encoding="utf-8")


def test_release_writes_keep_their_ask_rules():
    assert bootstrap.RELEASE_ASK_RULES == (
        "Bash(ws release publish:*)",
        "Bash(ws release move:*)",
    )
