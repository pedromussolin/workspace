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
        "ws observe close",
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


def run_section() -> str:
    text = SKILL.read_text()
    return text.split("### Run", 1)[1].split("\n### ", 1)[0]


def test_skill_runs_the_printed_record_and_fallback_lines():
    run = run_section()
    for phrase in ("observability.next", "observability.record", "observability.fallback"):
        assert phrase in run, phrase
    assert "--result <result_path>" not in run
    assert "same flags as" not in run


def test_skill_closes_a_done_observation():
    text = SKILL.read_text()
    close = text.split("### Close", 1)[1].split("\n## ", 1)[0]
    assert text.index("### Status") < text.index("### Close")
    for phrase in ("ws observe close TASK", "`done`", "--force", "ws observe report"):
        assert phrase in close, phrase


def test_daily_has_the_observation_line():
    text = (ROOT / "skills" / "daily" / "SKILL.md").read_text()
    assert "ws observe status --json" in text
    assert "observação:" in text


def test_change_request_survey_uses_the_report():
    text = (ROOT / "skills" / "change-request" / "SKILL.md").read_text()
    assert "ws observe report" in text
