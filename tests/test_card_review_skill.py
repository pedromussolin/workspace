from pathlib import Path

SKILL = Path(__file__).parent.parent / "skills" / "card-review" / "SKILL.md"


def test_skill_names_the_command_and_the_rules():
    text = SKILL.read_text()
    head = text.split("---")[1]
    assert "name: card-review" in head
    assert "disable-model-invocation" not in head
    for phrase in (
        "ws review pack",
        "use Read on its `diff_file`",
        "Never run git",
        "not even `diff_command`",
        "`diff --git a/<old_path> b/<path>`",
        "review.md",
        "pack.json",
        "## Olhar primeiro",
        "## Riscos",
        "done_when",
        "#L",
        "never commit",
        "nothing is written",
        "no `card`",
        "Never Read a null `abs_path`",
        "plain `path:line` without a link",
        'write "nenhuma alteração"',
        "`diff_file` null",
        "per-repo problems, warnings and flags start with `<repo>: `",
        "card-level ones",
    ):
        assert phrase in text, phrase
    assert "<diff_command> --" not in text
    assert len(text.splitlines()) < 500
