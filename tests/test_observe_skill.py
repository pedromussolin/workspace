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


def test_skill_backfills_missing_and_stale_days_first():
    run = run_section()
    first = run.split("\n2. ", 1)[0]
    for phrase in ("ws observe status --json", "missing_days", "stale", "oldest first"):
        assert phrase in first, phrase
    assert "ws observe run TASK --day" in first
    assert first.index("ws observe status --json") < run.index("as its own Bash call")


def test_skill_warns_before_editing_a_check_after_day_one():
    rules = SKILL.read_text().split("## Rules", 1)[1]
    assert "after day 1" in rules
    assert "stale" in rules
    assert "before" in rules


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


def test_daily_keeps_the_valid_plans_at_exit_1():
    text = (ROOT / "skills" / "daily" / "SKILL.md").read_text()
    step = text.split("3c. **Observations.**", 1)[1].split("\n4. ", 1)[0]
    for phrase in (
        "`pending`",
        "`done`",
        "`attention`",
        "`missing_days`",
        "`stale`",
        "Exit 1 with JSON on stdout",
        "each item of `problems` as one warning",
        "Exit 2",
        "no JSON",
    ):
        assert phrase in step, phrase
    assert "A non-zero exit" not in step
    note = text.split('one "observação: ', 1)[1].split("\n- ", 1)[0]
    assert "faltam dd/mm" in note


def test_readme_names_project_on_every_task_command_and_close():
    text = (ROOT / "README.md").read_text()
    rows = [line for line in text.splitlines() if line.startswith("| `ws observe ")]
    for command in ("run", "record", "report", "close"):
        [row] = [each for each in rows if each.startswith(f"| `ws observe {command} TASK")]
        assert "[--project SLUG]" in row.split("` |", 1)[0], command
    [new] = [each for each in rows if each.startswith("| `ws observe new ")]
    assert "`check TASK [--project SLUG]`" in new
    assert "`show TASK [--project SLUG] [--json]`" in new


def test_readme_names_what_the_box_cannot_see():
    text = (ROOT / "README.md").read_text()
    prose = text.split("## Observing a switched-off job", 1)[1].split("\n### ", 1)[0]
    assert "`bash obs.sh`" in prose
    assert "not seen by the box" in prose


def test_change_request_survey_uses_the_report():
    text = (ROOT / "skills" / "change-request" / "SKILL.md").read_text()
    assert "ws observe report" in text
