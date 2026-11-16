from test_card import START_FIELD, claude_settings, make_draft, passing, problems, world  # noqa: F401

TRANSITIONS_URL = "/rest/api/3/issue/TS-101/transitions"


def _overrides(ws_config, text):
    config = ws_config / "config.toml"
    config.write_text(
        config.read_text() + "\n[tracker.jira.status_overrides]\n" + text, encoding="utf-8"
    )


def _destination(name, category=None):
    destination = {"name": name}
    if category:
        destination["statusCategory"] = {"key": category}
    return destination


def test_move_by_status_picks_the_one_transition(world, capsys):  # noqa: F811
    path = make_draft("m.md", "move", key="TS-101", status="in_progress")

    verdict = passing(path, capsys)

    assert verdict["requests"] == [
        {"method": "POST", "path": TRANSITIONS_URL, "body": {"transition": {"id": "21"}}}
    ]


def test_move_by_status_with_two_destinations_names_them(world, capsys):  # noqa: F811
    world.set_transitions(
        "TS-101",
        [
            {"id": "1", "name": "A", "to": _destination("Fazendo", "indeterminate"), "fields": {}},
            {
                "id": "2",
                "name": "B",
                "to": _destination("Revisando", "indeterminate"),
                "fields": {},
            },
        ],
    )

    message = problems(make_draft("m.md", "move", key="TS-101", status="in_progress"), capsys)

    assert "Fazendo" in message and "Revisando" in message and "use to" in message


def test_move_by_status_with_no_destination_names_the_available_ones(world, capsys):  # noqa: F811
    message = problems(make_draft("m.md", "move", key="TS-101", status="cancelled"), capsys)

    assert "cancelled" in message and "Em Andamento" in message and "use to" in message


def test_move_with_to_and_status_is_refused(world, capsys):  # noqa: F811
    path = make_draft("m.md", "move", key="TS-101", to="Em Andamento", status="in_progress")

    assert "exactly one of to or status" in problems(path, capsys)


def test_move_with_neither_to_nor_status_is_refused(world, capsys):  # noqa: F811
    assert "missing key 'to'" in problems(make_draft("m.md", "move", key="TS-101"), capsys)


def test_move_with_an_unknown_status_is_refused(world, capsys):  # noqa: F811
    path = make_draft("m.md", "move", key="TS-101", status="doing")

    assert "status must be one of" in problems(path, capsys)


def test_status_override_wins_over_the_category(world, capsys, ws_config):  # noqa: F811
    _overrides(ws_config, '"Em Andamento" = "review"\n"Em Validação" = "in_progress"\n')

    verdict = passing(make_draft("m.md", "move", key="TS-101", status="in_progress"), capsys)

    assert verdict["requests"][0]["body"] == {"transition": {"id": "31"}}


def test_move_by_status_sets_an_empty_start_date(world, capsys):  # noqa: F811
    world.set_card("TS-101", **{START_FIELD: None})

    verdict = passing(make_draft("m.md", "move", key="TS-101", status="in_progress"), capsys)

    assert [r["method"] for r in verdict["requests"]] == ["POST", "PUT"]
    assert verdict["requests"][1]["body"] == {"fields": {START_FIELD: "2026-10-27"}}


def test_move_by_status_to_another_status_adds_no_start_date(world, capsys, ws_config):  # noqa: F811
    _overrides(ws_config, '"Em Validação" = "validation"\n')
    world.set_card("TS-101", **{START_FIELD: None})

    verdict = passing(make_draft("m.md", "move", key="TS-101", status="validation"), capsys)

    assert len(verdict["requests"]) == 1
