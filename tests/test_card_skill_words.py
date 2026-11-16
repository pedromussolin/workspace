from pathlib import Path

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
