"""The card policy in `ws card check` and `preview`: a company profile and a project layer change
how a draft is judged; the default policy (every other card test) is unchanged."""

import json
from datetime import date

import pytest
from test_card import (
    START_FIELD,
    approve,  # noqa: F401
    claude_settings,  # noqa: F401
    create_draft,
    make_draft,
    passing,
    preview,
    problems,
    world,  # noqa: F401
)

from ws.cli import main

PROFILE = """\
version = 1

[title]
format = "subgroup"

[sections.bug]
required = ["Problema", "Pronto quando"]
optional = []

[create]
require = ["epic", "estimate", "due", "categories"]

[estimate]
padding_percent = 20

[categories.label]
values = ["planned", "intruder-ops"]
required = true

[categories.tag]
values = ["BIG", "SMALL", "NEW"]
required = true

[categories.tag.derive]
from = "estimate"
threshold_hours = 6
above = "BIG"
at_most = "SMALL"
keep = ["NEW"]

[finish]
require = ["start", "time_spent"]
"""
TITLE = "[subgroup] - Texto"
DONE = {"id": "51", "name": "Fechar", "to": {"name": "Done", "statusCategory": {"key": "done"}}}
PADDING = "Estimativa original: confira se já inclui a folga de 20% do padrão."


@pytest.fixture
def profile(world, ws_config, tmp_path, monkeypatch):  # noqa: F811
    """The world with the fake company profile on, and a repo root with no projects."""
    (ws_config / "card-policies").mkdir()
    (ws_config / "card-policies" / "acme-like.toml").write_text(PROFILE, encoding="utf-8")
    config = ws_config / "config.toml"
    config.write_text(config.read_text(encoding="utf-8") + '\n[card]\npolicy = "acme-like"\n')
    root = tmp_path / "repo"
    (root / "projects").mkdir(parents=True)
    monkeypatch.setenv("WS_REPO_ROOT", str(root))
    world.root = root
    world.set_transitions("TS-101", [DONE])
    return world


def good(**front):
    values = {"labels": ["planned", "SMALL"], "estimate": "2h", "title": TITLE}
    values.update(front)
    return create_draft(**values)


def edit_draft(name="e.md", **front):
    return make_draft(name, "edit", key="TS-101", **front)


def test_create_with_a_subgroup_title_passes(profile, capsys):
    passing(good(), capsys)


def test_create_with_the_epic_prefix_title_fails(profile, capsys):
    message = problems(good(title="[FRONT] Título curto"), capsys)

    assert "the title must be '[group] - text'" in message
    assert "epic's prefix" not in message


def test_create_without_estimate_and_categories_fails(profile, capsys):
    message = problems(create_draft(title=TITLE), capsys)

    assert "estimate is required (card policy: create.require.estimate)" in message
    assert "group label needs exactly one value (planned, intruder-ops)" in message
    assert "group tag needs exactly one value (BIG, SMALL, NEW)" in message


def test_create_with_two_values_of_one_group_fails(profile, capsys):
    message = problems(good(labels=["planned", "intruder-ops", "SMALL"]), capsys)

    assert "group label takes at most one value, found planned, intruder-ops" in message


def test_create_with_a_tag_that_contradicts_the_estimate_fails(profile, capsys):
    message = problems(good(estimate="10h"), capsys)

    assert "group tag: SMALL contradicts the estimate of 10h; expected BIG" in message


def test_create_sections_come_from_the_policy_per_type(profile, capsys):
    path = good(type="bug")

    message = problems(path, capsys)

    assert "the description needs a '## Problema' section" in message
    assert "'## Contexto'" not in message and "Como reproduzir" not in message


def test_the_due_date_is_required_by_the_policy_without_a_sprint(profile, capsys):
    message = problems(good(due=None, sprint=None), capsys)

    assert "due is required (card policy: create.require.due)" in message


def test_the_padding_warning_is_in_the_check_and_in_the_preview(profile, capsys):
    path = good()

    assert PADDING in passing(path, capsys)["warnings"]
    out, _ = preview(path, capsys)
    assert f"  Aviso: {PADDING}\n" in out


def test_no_padding_warning_without_an_estimate_in_the_draft(profile, capsys):
    profile.set_card("TS-101", labels=["planned"])

    verdict = passing(edit_draft(title=TITLE), capsys)

    assert verdict["warnings"] == []


def test_edit_that_only_changes_the_title_to_a_subgroup_title_passes(profile, capsys):
    verdict = passing(edit_draft(title=TITLE), capsys)

    assert verdict["requests"][0]["body"] == {"fields": {"summary": TITLE}}


def test_edit_with_the_epic_prefix_title_fails(profile, capsys):
    assert "the title must be '[group] - text'" in problems(
        edit_draft(title="[FRONT] Outro"), capsys
    )


def test_edit_adding_a_tag_that_contradicts_the_estimate_fails(profile, capsys):
    profile.set_card(
        "TS-101",
        labels=["planned"],
        timetracking={"originalEstimate": "10h", "originalEstimateSeconds": 36000},
    )

    message = problems(edit_draft(add_labels=["SMALL"]), capsys)

    assert "group tag: SMALL contradicts the estimate of 10h; expected BIG" in message


def test_edit_adding_the_tag_the_estimate_expects_passes(profile, capsys):
    profile.set_card(
        "TS-101",
        labels=["planned"],
        timetracking={"originalEstimate": "10h", "originalEstimateSeconds": 36000},
    )

    passing(edit_draft(add_labels=["BIG"]), capsys)


def test_edit_changing_the_estimate_checks_the_tag_the_card_has(profile, capsys):
    profile.set_card("TS-101", labels=["planned", "SMALL"])

    message = problems(edit_draft(estimate="10h"), capsys)

    assert "group tag: SMALL contradicts the estimate of 10h; expected BIG" in message


def test_edit_does_not_ask_for_the_required_categories(profile, capsys):
    profile.set_card("TS-101", labels=[])

    passing(edit_draft(priority="High"), capsys)


def test_edit_description_is_checked_against_the_sections_of_the_new_type(profile, capsys):
    body = "## Contexto\nalgo\n\n## Pronto quando\n- ok\n"
    path = make_draft("e.md", "edit", body=body, key="TS-101", type="bug")

    message = problems(path, capsys)

    assert "the description needs a '## Problema' section" in message


def test_move_to_done_needs_the_start_date_and_time_spent(profile, capsys):
    profile.set_card("TS-101", fields={START_FIELD: None})
    path = make_draft("m.md", "move", key="TS-101", to="Done")

    message = problems(path, capsys)

    assert "the start date is not set (card policy: finish.require.start)" in message
    assert "no time spent is logged (card policy: finish.require.time_spent)" in message


def test_move_to_done_passes_with_the_start_and_the_time_spent_of_the_card(profile, capsys):
    profile.set_card("TS-101", timetracking={"timeSpentSeconds": 3600})

    passing(make_draft("m.md", "move", key="TS-101", to="Done"), capsys)


def test_move_to_done_counts_the_worklog_and_the_start_of_the_same_batch(profile, capsys):
    profile.set_card("TS-101", fields={START_FIELD: None})
    folder = make_draft("1-start.md", "edit", key="TS-101", start=date(2026, 10, 26)).parent
    make_draft("2-hours.md", "worklog", key="TS-101", time="2h", day=date(2026, 10, 26))
    make_draft("3-done.md", "move", key="TS-101", to="Done")

    out, _ = preview(folder, capsys)

    assert "Mover card TS-101" in out


def test_move_to_done_with_only_the_worklog_of_the_batch_still_needs_the_start(profile, capsys):
    profile.set_card("TS-101", fields={START_FIELD: None})
    folder = make_draft("2-hours.md", "worklog", key="TS-101", time="2h").parent
    make_draft("3-done.md", "move", key="TS-101", to="Done")

    assert main(["card", "preview", str(folder)]) == 1

    out = capsys.readouterr().out
    assert "the start date is not set" in out and "no time spent" not in out


def test_move_to_another_status_asks_nothing_of_the_policy(profile, capsys):
    profile.set_card("TS-101", fields={START_FIELD: None})
    profile.set_transitions(
        "TS-101", [{"id": "31", "name": "Validar", "to": {"name": "Em Validação"}, "fields": {}}]
    )

    passing(make_draft("m.md", "move", key="TS-101", to="Em Validação"), capsys)


def test_the_project_layer_of_the_epic_overrides_the_company_one(profile, capsys):
    folder = profile.root / "projects" / "alpha"
    folder.mkdir()
    (folder / "project.toml").write_text('epics = ["TS-100"]\n', encoding="utf-8")
    (folder / "card-policy.toml").write_text(
        'version = 1\n[title]\nformat = "epic_prefix"\n', encoding="utf-8"
    )

    passing(good(title="[FRONT] Título curto"), capsys)


def test_policy_prints_the_merged_document_and_its_sources(profile, capsys):
    assert main(["card", "policy"]) == 0

    document = json.loads(capsys.readouterr().out)
    assert document["policy"]["title"] == {"format": "subgroup"}
    assert document["policy"]["finish"] == {"require": ["start", "time_spent"]}
    assert document["sources"]["title"] == "company"
    assert document["sources"]["links"] == "default"


def test_policy_with_a_project_adds_its_layer(profile, capsys):
    folder = profile.root / "projects" / "alpha"
    folder.mkdir()
    (folder / "card-policy.toml").write_text(
        "version = 1\n[estimate]\npadding_percent = 0\n", encoding="utf-8"
    )

    assert main(["card", "policy", "--project", "alpha"]) == 0

    document = json.loads(capsys.readouterr().out)
    assert document["policy"]["estimate"]["padding_percent"] == 0
    assert document["sources"]["estimate"] == "project"
    assert document["sources"]["title"] == "company"


def test_policy_without_company_profile_is_the_default(world, capsys):  # noqa: F811
    assert main(["card", "policy"]) == 0

    document = json.loads(capsys.readouterr().out)
    assert document["policy"]["title"] == {"format": "epic_prefix"}
    assert set(document["sources"].values()) == {"default"}


def test_a_configured_profile_without_its_file_is_a_setup_error(profile, ws_config, capsys):
    (ws_config / "card-policies" / "acme-like.toml").unlink()
    path = good()

    assert main(["card", "check", str(path)]) == 2
    err = capsys.readouterr().err
    assert "acme-like.toml" in err and "is missing" in err
    assert main(["card", "policy"]) == 2
    assert "acme-like.toml" in capsys.readouterr().err


def test_an_invalid_layer_is_a_setup_error_naming_the_file(profile, ws_config, capsys):
    (ws_config / "card-policies" / "acme-like.toml").write_text(
        "version = 1\nbogus = 1\n", encoding="utf-8"
    )

    assert main(["card", "check", str(good())]) == 2

    err = capsys.readouterr().err
    assert "acme-like.toml" in err and "bogus" in err


def test_an_invalid_project_layer_is_a_setup_error_naming_the_file(profile, capsys):
    folder = profile.root / "projects" / "alpha"
    folder.mkdir()
    (folder / "card-policy.toml").write_text("version = 2\n", encoding="utf-8")

    assert main(["card", "policy", "--project", "alpha"]) == 2

    assert "card-policy.toml" in capsys.readouterr().err
