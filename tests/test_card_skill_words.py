from pathlib import Path

from ws.taskmodel import Status

CARD = Path(__file__).resolve().parent.parent / "skills" / "card"
VENDOR_WORDS = ("Jira", "Atlassian", "JQL", "atlassian.net")


def test_card_skill_names_no_vendor():
    for name in ("SKILL.md", "references/card-rules.md"):
        text = (CARD / name).read_text(encoding="utf-8")
        found = [word for word in VENDOR_WORDS if word in text]
        assert not found, f"{name} names {found}"


def test_card_skill_links_the_jira_reference():
    skill = (CARD / "SKILL.md").read_text(encoding="utf-8")
    assert skill.count("references/jira.md") == 1
    assert (CARD / "references" / "jira.md").is_file()


def test_card_skill_stays_under_500_lines():
    skill = (CARD / "SKILL.md").read_text(encoding="utf-8")
    assert len(skill.splitlines()) < 500


def test_card_skill_move_takes_to_or_a_neutral_status():
    skill = (CARD / "SKILL.md").read_text(encoding="utf-8")
    [row] = [line for line in skill.splitlines() if line.startswith("| `move` |")]

    assert "exactly one of `to`" in row
    assert all(f"`{status.value}`" in row for status in Status)


def test_card_skill_shows_a_draft_between_the_draft_and_the_preview():
    skill = (CARD / "SKILL.md").read_text(encoding="utf-8")
    show = skill.index("`ws card show <draft>`")

    assert skill.index("2. **Write the draft**") < show < skill.index("3. **Preview:**")
    assert skill.count("`ws card show <draft>`") == 1
