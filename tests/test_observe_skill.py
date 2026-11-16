from pathlib import Path

ROOT = Path(__file__).parent.parent
SKILL = ROOT / "skills" / "observe" / "SKILL.md"


def test_skill_names_the_commands_and_the_rules():
    text = SKILL.read_text()
    head = text.split("---")[1]
    assert "name: observe" in head
    assert "disable-model-invocation" not in head
    for phrase in (
        "ws observe new",
        "ws observe check",
        "ws observe run",
        "ws observe request",
        "ws observe fallback",
        "ws observe record",
        "ws observe status",
        "ws observe report",
        "verbatim",
        "observability.tool",
        "result_path",
        "never",
    ):
        assert phrase in text, phrase
    lowered = text.lower()
    for word in ("datadog", "postgres", "psql", "jira", "execute_code"):
        assert word not in lowered, word
    assert len(text.splitlines()) < 500


def test_daily_has_the_observation_line():
    text = (ROOT / "skills" / "daily" / "SKILL.md").read_text()
    assert "ws observe status --json" in text
    assert "observação:" in text


def test_change_request_survey_uses_the_report():
    text = (ROOT / "skills" / "change-request" / "SKILL.md").read_text()
    assert "ws observe report" in text
