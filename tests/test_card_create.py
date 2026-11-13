import json
from datetime import date

import pytest
from test_card import (
    SECTIONS,
    SPRINT_FIELD,
    approve,
    claude_settings,  # noqa: F401
    create_draft,
    make_draft,
    passing,
    preview,
    problems,
    world,  # noqa: F401
)

from ws.config import data_dir
from ws.identity import dev_id

NOT_YOURS = "card {key} is not yours: you are neither its assignee nor its reporter"

WRITE_OPS = {
    "edit": lambda key: make_draft("o.md", "edit", key=key, priority="High"),
    "move": lambda key: make_draft("o.md", "move", key=key, to="Em Validação"),
    "comment": lambda key: make_draft("o.md", "comment", "Oi.\n", key=key),
}


@pytest.mark.parametrize("op", sorted(WRITE_OPS))
def test_write_card_where_i_am_reporter_passes(world, capsys, op):  # noqa: F811
    world.set_card("TS-104", assignee="acc-other", reporter={"accountId": "acc-me"})
    world.set_transitions("TS-104", [{"id": "31", "to": {"name": "Em Validação"}, "fields": {}}])

    passing(WRITE_OPS[op]("TS-104"), capsys)


@pytest.mark.parametrize("op", sorted(WRITE_OPS))
def test_write_card_of_anyone_else_is_refused(world, capsys, op):  # noqa: F811
    world.set_card("TS-104", assignee="acc-other", reporter={"accountId": "acc-other"})
    world.set_transitions("TS-104", [{"id": "31", "to": {"name": "Em Validação"}, "fields": {}}])

    assert NOT_YOURS.format(key="TS-104") in problems(WRITE_OPS[op]("TS-104"), capsys)
    assert world.writes() == []


def test_create_sends_the_type_id(world, capsys):  # noqa: F811
    world.fake.routes[("GET", "/rest/api/3/issue/createmeta/TS/issuetypes/6")] = (
        200,
        json.dumps({"fields": [{"fieldId": "priority", "allowedValues": [{"name": "High"}]}]}),
    )
    path = create_draft(type="improvement")

    verdict = passing(path, capsys)
    out, _ = preview(path, capsys)

    assert verdict["requests"][0]["body"]["fields"]["issuetype"] == {"id": "6"}
    assert "Tipo: Melhoria" in out


def test_create_priorities_come_from_the_type_id(world, capsys):  # noqa: F811
    world.fake.routes[("GET", "/rest/api/3/issue/createmeta/TS/issuetypes/6")] = (
        200,
        json.dumps({"fields": [{"fieldId": "priority", "allowedValues": [{"name": "Low"}]}]}),
    )

    assert "priority 'High' is not allowed; the project accepts Low" in problems(
        create_draft(type="improvement"), capsys
    )
    assert world.requests_to("GET", "/rest/api/3/issue/createmeta/TS/issuetypes/6")


def test_create_type_without_an_id_is_a_problem(world, ws_config, capsys):  # noqa: F811
    config = ws_config / "config.toml"
    config.write_text(config.read_text().replace('improvement = "6"\n', ""), encoding="utf-8")

    assert (
        "type 'improvement' has no issue type id: add it to [jira.types] (ws tracker discover)"
        in problems(create_draft(type="improvement"), capsys)
    )


def test_create_assignee_and_reporter_from_dev_ids(world, capsys):  # noqa: F811
    world.fake.routes[("GET", "/rest/api/3/user")] = (
        200,
        json.dumps({"accountId": "acc-ana", "displayName": "ana"}),
    )
    path = create_draft(assignee=dev_id("ana@example.com"))

    fields = passing(path, capsys)["requests"][0]["body"]["fields"]
    out, _ = preview(path, capsys)

    assert fields["assignee"] == {"accountId": "acc-ana"}
    assert fields["reporter"] == {"accountId": "acc-me"}
    assert world.requests_to("GET", "/rest/api/3/user")[0]["query"] == {"accountId": "acc-ana"}
    assert "Responsável: ana" in out
    assert "Relator: Dev Example" in out


def test_create_reporter_can_be_someone_else_and_me_is_the_user(world, capsys):  # noqa: F811
    path = create_draft(reporter=dev_id("ana@example.com"), assignee="me")

    fields = passing(path, capsys)["requests"][0]["body"]["fields"]

    assert fields["reporter"] == {"accountId": "acc-ana"}
    assert fields["assignee"] == {"accountId": "acc-me"}


def test_create_own_dev_id_is_the_user(world, capsys):  # noqa: F811
    fields = passing(create_draft(assignee=dev_id("dev@example.com")), capsys)["requests"][0][
        "body"
    ]["fields"]

    assert fields["assignee"] == {"accountId": "acc-me"}


def test_create_person_name_falls_back_to_the_label(world, ws_config, capsys):  # noqa: F811
    config = ws_config / "config.toml"
    config.write_text(
        config.read_text().replace('jira = "acc-ana"', 'jira = "acc-ana"\nlabel = "Ana L"'),
        encoding="utf-8",
    )

    out, _ = preview(create_draft(assignee=dev_id("ana@example.com")), capsys)

    assert "Responsável: Ana L" in out


def test_create_unknown_dev_id_is_a_problem(world, capsys):  # noqa: F811
    unknown = dev_id("nobody@example.com")

    assert (
        f"unknown person {unknown!r}: run ws people add <e-mail> and paste the block into "
        "config.toml" in problems(create_draft(assignee=unknown), capsys)
    )


def test_create_dev_id_without_jira_id_is_a_problem(world, ws_config, capsys):  # noqa: F811
    bia = dev_id("bia@example.com")
    config = ws_config / "config.toml"
    config.write_text(config.read_text() + f'\n[people."{bia}"]\nlabel = "bia"\n', "utf-8")

    assert f"person {bia!r} has no jira id" in problems(create_draft(assignee=bia), capsys)


def test_create_without_sprint_sends_no_sprint_and_reads_no_board(world, capsys):  # noqa: F811
    path = create_draft(sprint=None)

    verdict = passing(path, capsys)
    out, _ = preview(path, capsys)

    assert SPRINT_FIELD not in verdict["requests"][0]["body"]["fields"]
    assert world.requests_to("GET", "/rest/agile/1.0/board/7/sprint") == []
    assert "Sprint: (nenhuma)" in out


def test_create_with_sprint_active_keeps_todays_rules(world, capsys):  # noqa: F811
    path = create_draft(sprint="active")
    world.set_sprints([])

    assert "exactly one active sprint, found 0" in problems(path, capsys)
    world.set_sprints([{"id": 55, "name": "Sprint 55", "endDate": "2026-11-10T15:00:00.000Z"}])
    fields = passing(path, capsys)["requests"][0]["body"]["fields"]
    assert fields[SPRINT_FIELD] == 55


def test_create_due_is_optional_without_sprint(world, capsys):  # noqa: F811
    path = create_draft(sprint=None, due=None)

    verdict = passing(path, capsys)
    out, _ = preview(path, capsys)

    assert "duedate" not in verdict["requests"][0]["body"]["fields"]
    assert "Prazo: (nenhum)" in out


def test_create_due_is_required_with_sprint(world, capsys):  # noqa: F811
    assert 'due is required with sprint = "active"' in problems(
        create_draft(sprint="active", due=None), capsys
    )


def test_create_past_due_is_still_refused(world, capsys):  # noqa: F811
    assert "is before today" in problems(create_draft(sprint=None, due=date(2026, 10, 1)), capsys)


def test_create_bug_needs_reproduction_and_evidence(world, capsys):  # noqa: F811
    world.fake.routes[("GET", "/rest/api/3/issue/createmeta/TS/issuetypes/4")] = (
        200,
        json.dumps({"fields": [{"fieldId": "priority", "allowedValues": [{"name": "High"}]}]}),
    )
    path = create_draft(type="bug", body=SECTIONS + "\n## Evidência\nlog\n")

    assert "the description needs a '## Como reproduzir' section" in problems(path, capsys)

    full = SECTIONS + "\n## Como reproduzir\n1. abrir\n\n## Evidência\nlog\n"
    passing(create_draft(type="bug", body=full), capsys)


def test_create_hotfix_needs_why_not_the_release(world, capsys):  # noqa: F811
    world.fake.routes[("GET", "/rest/api/3/issue/createmeta/TS/issuetypes/5")] = (
        200,
        json.dumps({"fields": [{"fieldId": "priority", "allowedValues": [{"name": "High"}]}]}),
    )
    body = SECTIONS + "\n## Como reproduzir\n1. abrir\n\n## Evidência\nlog\n"

    assert "the description needs a '## Por que não espera a release' section" in problems(
        create_draft(type="hotfix", body=body), capsys
    )


def test_created_cards_are_logged(world, capsys):  # noqa: F811
    path = create_draft()
    _, code = preview(path, capsys)

    assert approve(path, code) == 0

    log = data_dir() / "cards" / "created.tsv"
    assert log.read_text(encoding="utf-8") == "create.md\tTS-200\t2026-10-27\n"
