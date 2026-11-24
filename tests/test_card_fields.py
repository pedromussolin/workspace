"""Labels and the original estimate of a card: the check, the requests, the preview, the apply."""

import json

import pytest
from test_card import (
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
from ws.tracker.jira import writer

ESTIMATE_PUT = ("PUT", "/rest/api/3/issue/TS-200")


def edit_draft(name="e.md", **front):
    return make_draft(name, "edit", key="TS-101", **front)


def body_of(verdict):
    [request] = verdict["requests"]
    return request["body"]


def test_create_sends_the_labels_and_shows_them(world, capsys):  # noqa: F811
    path = create_draft(labels=["planejado", "dados"])

    verdict = passing(path, capsys)

    assert body_of(verdict)["fields"]["labels"] == ["planejado", "dados"]
    assert "  Categorias: planejado, dados\n" in preview(path, capsys)[0]


def test_create_without_labels_or_estimate_sends_neither_and_shows_neither(world, capsys):  # noqa: F811
    path = create_draft()

    fields = body_of(passing(path, capsys))["fields"]

    assert "labels" not in fields and "timetracking" not in fields
    out = preview(path, capsys)[0]
    assert "Categorias" not in out and "Estimativa" not in out


def test_create_labels_with_whitespace_are_refused(world, capsys):  # noqa: F811
    message = problems(create_draft(labels=["ok", "dois nomes"]), capsys)

    assert "label 'dois nomes' has whitespace" in message


def test_create_labels_need_the_create_screen_to_have_them(world, capsys):  # noqa: F811
    world.set_create_screen("3", without=("labels",))

    assert "the create screen of Tarefa has no labels" in problems(
        create_draft(labels=["a"]), capsys
    )


def test_create_estimate_goes_in_the_create_when_the_screen_has_it(world, capsys):  # noqa: F811
    world.set_create_screen("3", extra=("timetracking",))
    path = create_draft(estimate="2h  30m")

    verdict = passing(path, capsys)

    assert body_of(verdict)["fields"]["timetracking"] == {"originalEstimate": "2h 30m"}
    assert "  Estimativa original: 2h 30m\n" in preview(path, capsys)[0]


def test_create_estimate_without_the_field_on_the_screen_is_a_second_request(world, capsys):  # noqa: F811
    verdict = passing(create_draft(estimate="10h"), capsys)

    first, second = verdict["requests"]
    assert "timetracking" not in first["body"]["fields"]
    assert second == {
        "method": "PUT",
        "path": "/rest/api/3/issue/{created}",
        "body": {"fields": {"timetracking": {"originalEstimate": "10h"}}},
    }


@pytest.mark.parametrize("estimate", ["2", "1.5h", "0h", "1h 1h", "2h30", "1d"])
def test_create_estimate_format_is_the_worklog_one(world, capsys, estimate):  # noqa: F811
    assert "estimate" in problems(create_draft(estimate=estimate), capsys)


def test_one_code_creates_the_card_then_sets_its_estimate_on_the_new_key(world, capsys):  # noqa: F811
    world.fake.routes[ESTIMATE_PUT] = (204, "")
    path = create_draft(labels=["planejado"], estimate="10h")
    out, code = preview(path, capsys)

    assert approve(path, code) == 0

    assert [(r["method"], r["path"]) for r in world.writes()] == [
        ("POST", "/rest/api/3/issue"),
        ESTIMATE_PUT,
    ]
    assert world.writes()[1]["body"] == {"fields": {"timetracking": {"originalEstimate": "10h"}}}
    assert "Criado: create.md" in capsys.readouterr().out


def test_a_failing_estimate_after_the_create_reports_the_card_as_created(world, capsys):  # noqa: F811
    world.fake.routes[ESTIMATE_PUT] = (400, json.dumps({"errorMessages": ["no field"]}))
    path = create_draft(estimate="10h")
    _, code = preview(path, capsys)
    capsys.readouterr()

    assert approve(path, code) == 3

    text = capsys.readouterr().out
    assert "create.md: o card TS-200 foi criado (" in text
    assert "/browse/TS-200" in text and "a estimativa original) não foi aplicado" in text
    assert "o Jira recusou" in text and "no field" in text
    assert "create.md\tTS-200\t" in (data_dir() / "cards" / "created.tsv").read_text()
    assert "Para procurar o card" not in text


def test_an_uncertain_estimate_after_the_create_does_not_look_for_the_card(world, capsys):  # noqa: F811
    world.fake.routes[ESTIMATE_PUT] = (500, "{}")
    path = create_draft(estimate="10h")
    _, code = preview(path, capsys)
    capsys.readouterr()

    assert approve(path, code) == 3

    text = capsys.readouterr().out
    assert "o card TS-200 foi criado" in text and "resultado incerto" in text
    assert "Para procurar o card" not in text


def test_the_new_key_must_pass_the_guard_before_the_second_request(world, capsys):  # noqa: F811
    world.fake.routes[("POST", "/rest/api/3/issue")] = (201, json.dumps({"key": "OTHER-9"}))
    path = create_draft(estimate="10h")
    _, code = preview(path, capsys)
    capsys.readouterr()

    assert approve(path, code) == 3

    assert [r["method"] for r in world.writes()] == ["POST"]
    assert "leads outside the allowed requests" in capsys.readouterr().out


def test_the_placeholder_path_is_allowed_by_the_guard_only_as_a_put():
    put = {"method": "PUT", "path": "/rest/api/3/issue/{created}", "body": {}}

    assert writer.guard("TS", [put]) is None
    assert writer.guard("TS", [{**put, "method": "DELETE"}]) is not None
    assert writer.guard("TS", [{**put, "path": "/rest/api/3/issue/{other}"}]) is not None


def test_edit_adds_and_removes_labels_without_replacing_the_list(world, capsys):  # noqa: F811
    world.set_card("TS-101", labels=["velho", "fica"])
    path = edit_draft(add_labels=["novo"], remove_labels=["velho"])

    verdict = passing(path, capsys)

    assert verdict["requests"] == [
        {
            "method": "PUT",
            "path": "/rest/api/3/issue/TS-101",
            "body": {"update": {"labels": [{"add": "novo"}, {"remove": "velho"}]}},
        }
    ]
    assert "  Categorias: + novo, - velho\n" in preview(path, capsys)[0]


def test_edit_skips_a_label_already_there_and_one_already_absent(world, capsys):  # noqa: F811
    world.set_card("TS-101", labels=["fica"])
    path = edit_draft(add_labels=["fica", "novo"], remove_labels=["nunca-teve"])

    body = body_of(passing(path, capsys))

    assert body == {"update": {"labels": [{"add": "novo"}]}}
    assert "  Categorias: + novo\n" in preview(path, capsys)[0]


def test_edit_that_only_skips_labels_changes_nothing(world, capsys):  # noqa: F811
    world.set_card("TS-101", labels=["fica"])

    message = problems(edit_draft(add_labels=["fica"], remove_labels=["nunca-teve"]), capsys)

    assert message == "the draft changes nothing on the card"


def test_edit_label_in_both_lists_is_refused(world, capsys):  # noqa: F811
    message = problems(edit_draft(add_labels=["a", "b"], remove_labels=["b"]), capsys)

    assert message == "b is in add_labels and in remove_labels"


def test_edit_label_with_whitespace_is_refused(world, capsys):  # noqa: F811
    assert "has whitespace" in problems(edit_draft(add_labels=["dois nomes"]), capsys)


def test_edit_cannot_replace_the_whole_list_of_labels(world, capsys):  # noqa: F811
    assert "unknown key 'labels' for op edit" in problems(edit_draft(labels=["a"]), capsys)


def test_edit_labels_and_fields_travel_in_one_request(world, capsys):  # noqa: F811
    path = edit_draft(title="[FRONT] Novo título", add_labels=["novo"])

    assert body_of(passing(path, capsys)) == {
        "fields": {"summary": "[FRONT] Novo título"},
        "update": {"labels": [{"add": "novo"}]},
    }


@pytest.mark.parametrize(
    ("front", "field"),
    [({"add_labels": ["a"]}, "labels"), ({"estimate": "1h"}, "timetracking")],
)
def test_edit_names_a_field_missing_from_the_edit_screen(world, capsys, front, field):  # noqa: F811
    world.set_edit_screen("TS-101", without=(field,))

    assert problems(edit_draft(**front), capsys) == f"the edit screen of TS-101 has no {field}"


def test_edit_estimate_sets_the_original_estimate_and_shows_the_old_one(world, capsys):  # noqa: F811
    world.set_card(
        "TS-101", timetracking={"originalEstimate": "5h", "originalEstimateSeconds": 18000}
    )
    path = edit_draft(estimate="10h")

    verdict = passing(path, capsys)

    assert body_of(verdict) == {"fields": {"timetracking": {"originalEstimate": "10h"}}}
    assert "  Estimativa original: 5h -> 10h\n" in preview(path, capsys)[0]


def test_edit_estimate_without_a_current_one(world, capsys):  # noqa: F811
    path = edit_draft(estimate="45m")

    passing(path, capsys)

    assert "  Estimativa original: (nenhuma) -> 45m\n" in preview(path, capsys)[0]


def test_edit_estimate_equal_to_the_current_one_changes_nothing(world, capsys):  # noqa: F811
    world.set_card(
        "TS-101", timetracking={"originalEstimate": "1d 2h", "originalEstimateSeconds": 36000}
    )

    assert problems(edit_draft(estimate="10h"), capsys) == "the draft changes nothing on the card"


def test_edit_estimate_format_is_the_worklog_one(world, capsys):  # noqa: F811
    assert "estimate must be hours and minutes only" in problems(edit_draft(estimate="2"), capsys)


def test_edit_of_labels_is_applied_as_the_planned_update(world, capsys):  # noqa: F811
    world.set_card("TS-101", labels=["velho"])
    path = edit_draft(add_labels=["novo"], remove_labels=["velho"])
    _, code = preview(path, capsys)

    assert approve(path, code) == 0

    [sent] = world.writes()
    assert sent["body"] == {"update": {"labels": [{"add": "novo"}, {"remove": "velho"}]}}
