from pathlib import Path

from ws.standupreport import build_report
from ws.tracker.jira.client import FIELDS

DAILY = Path(__file__).resolve().parent.parent / "skills" / "daily"
VENDOR_WORDS = (
    "getAccessibleAtlassianResources",
    "searchJiraIssuesUsingJql",
    "atlassianUserInfo",
    "cloudId",
    "Atlassian",
    "Jira",
    "JQL",
)


def test_daily_skill_names_no_vendor():
    for name in ("SKILL.md", "references/detailed.md", "references/period.md"):
        text = (DAILY / name).read_text(encoding="utf-8")
        found = [word for word in VENDOR_WORDS if word in text]
        assert not found, f"{name} names {found}"


def test_daily_fallback_follows_the_kind_reference():
    skill = (DAILY / "SKILL.md").read_text(encoding="utf-8")
    assert "references/<kind>.md" in skill
    assert "[tracker] kind" in skill
    reference = (DAILY / "references" / "jira.md").read_text(encoding="utf-8")
    for call in (
        "getAccessibleAtlassianResources",
        "atlassianUserInfo",
        "searchJiraIssuesUsingJql",
    ):
        assert call in reference
    assert "[tracker.jira] site" in reference and "[jira] site" in reference


def test_daily_reference_reads_the_old_table_when_tracker_jira_is_absent():
    """A config may have `[tracker] kind` and still the old `[jira]` table."""
    reference = " ".join((DAILY / "references" / "jira.md").read_text(encoding="utf-8").split())

    assert "or `[jira] site` when there is no `[tracker.jira]` table" in reference
    assert "no `[tracker]` table" not in reference


def test_daily_reads_the_tracker_key():
    for name in ("SKILL.md", "references/detailed.md", "references/period.md"):
        text = (DAILY / name).read_text(encoding="utf-8")
        assert "`tracker`" in text, name


def test_report_has_tracker_key_not_jira():
    activity = {
        "window": {"since": "2026-10-26", "until": "2026-10-27"},
        "commits": [],
        "branches": [],
        "prs": [],
        "last_activity": {},
        "next_steps": [],
        "warnings": [],
    }
    from datetime import date

    report = build_report(activity, None, date(2026, 10, 27), None)
    assert report["tracker"] is False
    assert "jira" not in report


def test_daily_skill_points_to_the_period_reference_and_stays_small():
    skill = (DAILY / "SKILL.md").read_text(encoding="utf-8")
    assert "references/period.md" in skill
    assert len(skill.splitlines()) < 500
    for text in ("daily da semana passada", "texto para o gestor", "para a 1:1"):
        assert text in skill.split("---", 2)[1]


def test_period_reference_uses_the_commands_that_exist():
    reference = (DAILY / "references" / "period.md").read_text(encoding="utf-8")
    for command in ("ws standup period", "ws standup collect --since", "ws standup summary"):
        assert command in reference
    assert "never the person" in reference


def test_jira_reference_asks_for_the_period_fields_as_the_script():
    reference = (DAILY / "references" / "jira.md").read_text(encoding="utf-8")
    for field in ("statuscategorychangedate", "resolutiondate"):
        assert field in FIELDS
        assert f'"{field}"' in reference, field
    assert "`status_changed`" in reference and "`resolved`" in reference
