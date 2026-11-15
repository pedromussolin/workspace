from pathlib import Path

SKILL = Path(__file__).parent.parent / "skills" / "card-review" / "SKILL.md"


def test_skill_names_the_command_and_the_rules():
    text = SKILL.read_text()
    head = text.split("---")[1]
    assert "name: card-review" in head
    assert "disable-model-invocation" not in head
    for phrase in (
        "ws review pack",
        "diff_command",
        "review.md",
        "pack.json",
        "## Olhar primeiro",
        "## Riscos",
        "done_when",
        "#L",
        "never commit",
    ):
        assert phrase in text, phrase
    assert len(text.splitlines()) < 500
