import json
import os
import stat
from datetime import UTC, date, datetime, timedelta
from pathlib import Path

import pytest

from ws import card, cardrules
from ws.adf import to_adf
from ws.carddraft import DraftError, parse_draft
from ws.cli import main
from ws.config import data_dir
from ws.userconfig import save_jira_token

EMAIL = "dev@example.com"
START_FIELD = "customfield_10015"
SPRINT_FIELD = "customfield_10020"
NOW = datetime(2026, 10, 27, 15, 0, tzinfo=UTC)

SECTIONS = "## Contexto\nAlgo a explicar.\n\n## Pronto quando\n- feito\n"


def _fields(summary, *, assignee="acc-me", level=None, category="indeterminate", **extra):
    fields = {
        "summary": summary,
        "status": {"name": "In Progress", "statusCategory": {"key": category}},
        "project": {"key": "TS"},
        "assignee": {"accountId": assignee, "displayName": "Dev Example"} if assignee else None,
    }
    if level is not None:
        fields["issuetype"] = {"hierarchyLevel": level, "name": "Epic"}
    fields.update(extra)
    return fields


class World:
    def __init__(self, fake):
        self.fake = fake
        self.set_issue("TS-100", _fields("[FRONT] Épico de exemplo", level=1))
        self.set_issue("TS-110", _fields("Épico sem prefixo", level=1))
        self.set_issue("TS-111", _fields("[BACK] Outro épico", level=1))
        self.set_issue("TS-120", _fields("[FRONT] Tarefa", level=0))
        self.set_issue("TS-121", _fields("[FRONT] Épico feito", level=1, category="done"))
        self.set_issue("TS-130", _fields("[FRONT] Épico de outro projeto", level=1, project=None))
        self.fake.routes[("GET", "/rest/api/3/issue/TS-130")] = (
            200,
            json.dumps(
                {
                    "key": "TS-130",
                    "fields": {**_fields("[FRONT] x", level=1), "project": {"key": "OTHER"}},
                }
            ),
        )
        self.set_card("TS-101")
        self.set_card("TS-102", assignee="acc-other")
        self.set_card("TS-103", assignee=None)
        self.set_myself()
        self.set_sprints([{"id": 55, "name": "Sprint 55", "endDate": "2026-11-10T15:00:00.000Z"}])
        self.set_transitions(
            "TS-101",
            [
                {"id": "31", "name": "Validar", "to": {"name": "Em Validação"}, "fields": {}},
                {
                    "id": "41",
                    "name": "Concluir",
                    "to": {"name": "Done"},
                    "fields": {"resolution": {"required": True, "name": "Resolution"}},
                },
            ],
        )
        self.fake.routes[("GET", "/rest/api/3/issue/createmeta/TS/issuetypes")] = (
            200,
            json.dumps({"issueTypes": [{"id": "3", "name": "Tarefa"}]}),
        )
        self.fake.routes[("GET", "/rest/api/3/issue/createmeta/TS/issuetypes/3")] = (
            200,
            json.dumps(
                {
                    "fields": [
                        {
                            "fieldId": "priority",
                            "allowedValues": [{"name": "High"}, {"name": "Medium"}],
                        }
                    ]
                }
            ),
        )
        self.fake.routes[("POST", "/rest/api/3/issue")] = (201, json.dumps({"key": "TS-200"}))
        self.fake.routes[("PUT", "/rest/api/3/issue/TS-101")] = (204, "")
        self.fake.routes[("POST", "/rest/api/3/issue/TS-101/transitions")] = (204, "")
        self.fake.routes[("POST", "/rest/api/3/issue/TS-101/comment")] = (201, "{}")
        self.fake.routes[("POST", "/rest/api/3/issue/TS-101/worklog")] = (201, "{}")

    def set_issue(self, key, fields):
        self.fake.routes[("GET", f"/rest/api/3/issue/{key}")] = (
            200,
            json.dumps({"key": key, "fields": fields}),
        )

    def set_card(self, key, assignee="acc-me", **overrides):
        fields = _fields(
            "[FRONT] Tela de exemplo",
            assignee=assignee,
            parent={"key": "TS-100", "fields": {"summary": "[FRONT] Épico de exemplo"}},
            description=to_adf(SECTIONS),
            priority={"name": "Medium"},
            duedate="2026-11-05",
            **{START_FIELD: "2026-10-26"},
        )
        fields.update(overrides.pop("fields", {}))
        fields.update(overrides)
        self.set_issue(key, fields)

    def set_myself(self, zone="America/Sao_Paulo"):
        body = {"accountId": "acc-me", "displayName": "Dev Example", "timeZone": zone}
        self.fake.routes[("GET", "/rest/api/3/myself")] = (200, json.dumps(body))

    def set_sprints(self, sprints):
        self.fake.routes[("GET", "/rest/agile/1.0/board/7/sprint")] = (
            200,
            json.dumps({"values": sprints}),
        )

    def set_transitions(self, key, transitions):
        self.fake.routes[("GET", f"/rest/api/3/issue/{key}/transitions")] = (
            200,
            json.dumps({"transitions": transitions}),
        )

    def writes(self):
        return [r for r in self.fake.requests if r["method"] != "GET"]

    def requests_to(self, method, path):
        return [r for r in self.fake.requests if (r["method"], r["path"]) == (method, path)]


def write_claude_settings(path, ask=("Bash(ws card apply:*)",), hook=True):
    gates = {"permissions": {"ask": list(ask)}}
    if hook:
        command = 'python3 -I "/srv/ws/hooks/ask_card_apply.py"'
        gates["hooks"] = {
            "PreToolUse": [{"matcher": "Bash", "hooks": [{"type": "command", "command": command}]}]
        }
    path.write_text(json.dumps(gates), encoding="utf-8")


@pytest.fixture
def claude_settings(tmp_path, monkeypatch):
    path = tmp_path / "claude-settings.json"
    write_claude_settings(path)
    monkeypatch.setenv("WS_CLAUDE_SETTINGS", str(path))
    return path


@pytest.fixture
def world(ws_config, fake_jira, monkeypatch, claude_settings):
    (ws_config / "config.toml").write_text(
        f'[jira]\nsite = "{fake_jira.site}"\nemail = "{EMAIL}"\nproject = "TS"\n'
        f'board_id = 7\nissue_type = "Tarefa"\nstart_date_field = "{START_FIELD}"\n'
        f'sprint_field = "{SPRINT_FIELD}"\n',
        encoding="utf-8",
    )
    save_jira_token("sample-value")
    monkeypatch.setattr(card, "_now", lambda: NOW)
    return World(fake_jira)


def _toml(value):
    return value.isoformat() if isinstance(value, date) else json.dumps(value, ensure_ascii=False)


def make_draft(name, op, body="", **front):
    folder = data_dir() / "cards" / "drafts"
    folder.mkdir(parents=True, exist_ok=True)
    lines = [f'op = "{op}"', *(f"{key} = {_toml(value)}" for key, value in front.items())]
    path = folder / name
    path.write_text("+++\n" + "\n".join(lines) + "\n+++\n" + body, encoding="utf-8")
    return path


def create_draft(name="create.md", title="[FRONT] Título curto", body=SECTIONS, **front):
    values = {"epic": "TS-100", "priority": "High", "due": date(2026, 10, 31)}
    values.update(front)
    values = {key: value for key, value in values.items() if value is not None}
    return make_draft(name, "create", f"# {title}\n\n{body}", **values)


def check(path, capsys):
    code = main(["card", "check", str(path)])
    return code, json.loads(capsys.readouterr().out)


def problems(path, capsys):
    code, verdict = check(path, capsys)
    assert code == 1
    assert verdict["ok"] is False
    return " | ".join(verdict["problems"])


def passing(path, capsys):
    code, verdict = check(path, capsys)
    assert (code, verdict["problems"]) == (0, [])
    assert verdict["ok"] is True
    return verdict


def test_draft_accepts_toml_dates_and_strings():
    raw = (
        b'+++\nop = "create"\nepic = "TS-1"\npriority = "High"\n'
        b'due = 2026-10-31\nstart = "2026-10-28"\n+++\n# T\n\nx\n'
    )

    draft = parse_draft(raw)

    assert draft.values["due"] == date(2026, 10, 31)
    assert draft.values["start"] == date(2026, 10, 28)
    assert draft.title == "T"


@pytest.mark.parametrize(
    "raw, message",
    [
        (b'+++\nop = "move"\nkey = "TS-1"\nto = "X"\nextra = 1\n+++\n', "unknown key 'extra'"),
        (b'+++\nop = "move"\nkey = "TS-1"\n+++\n', "missing key 'to'"),
        (b'+++\nop = "jump"\n+++\n', "op must be one of"),
        (b'op = "move"\n', "must start with"),
        (b'+++\nop = "move"\n', "not closed"),
        (b'+++\nop = "move\n+++\n', "not valid TOML"),
        (
            b'+++\nop = "worklog"\nkey = "TS-1"\ntime = "1h"\nday = 2026-10-27T10:00:00\n+++\n',
            "day",
        ),
        (b'+++\nop = "worklog"\nkey = "TS-1"\ntime = "1h"\nday = "ontem"\n+++\n', "day"),
        (b'+++\nop = "move"\nkey = ""\nto = "X"\n+++\n', "key must be"),
        (
            b'+++\nop = "create"\nepic = "T"\npriority = "H"\ndue = 2026-10-31\n+++\ntext\n',
            "# title",
        ),
        (b"\xff\xfe", "UTF-8"),
    ],
)
def test_draft_errors(raw, message):
    with pytest.raises(DraftError, match=message):
        parse_draft(raw)


def test_create_check_passes_and_builds_the_request(world, capsys):
    verdict = passing(create_draft(start=date(2026, 10, 28)), capsys)

    assert verdict["resolved"]["sprint"] == {
        "id": 55,
        "name": "Sprint 55",
        "end_date": "2026-11-10",
    }
    assert verdict["resolved"]["epic"] == {
        "key": "TS-100",
        "title": "[FRONT] Épico de exemplo",
        "prefix": "[FRONT]",
    }
    [request] = verdict["requests"]
    assert request["method"] == "POST"
    assert request["path"] == "/rest/api/3/issue"
    fields = request["body"]["fields"]
    assert fields == {
        "project": {"key": "TS"},
        "issuetype": {"name": "Tarefa"},
        "summary": "[FRONT] Título curto",
        "description": to_adf(SECTIONS),
        "parent": {"key": "TS-100"},
        "priority": {"name": "High"},
        "assignee": {"accountId": "acc-me"},
        START_FIELD: "2026-10-28",
        "duedate": "2026-10-31",
        SPRINT_FIELD: 55,
    }
    assert world.writes() == []


def test_create_start_defaults_to_today_in_the_users_zone(world, capsys):
    verdict = passing(create_draft(start=None), capsys)

    assert verdict["requests"][0]["body"]["fields"][START_FIELD] == "2026-10-27"


@pytest.mark.parametrize(
    "epic, message",
    [
        ("TS-130", "does not belong to project TS"),
        ("OTHER-1", "not a card of project TS"),
        ("TS-1", "was not found"),
        ("TS-120", "is not an epic"),
        ("TS-121", "is done"),
        ("ts-100", "not a card of project TS"),
    ],
)
def test_create_epic_rules_fail(world, capsys, epic, message):
    assert message in problems(create_draft(epic=epic), capsys)
    assert world.writes() == []


def test_create_epic_in_the_project_passes(world, capsys):
    passing(create_draft(epic="TS-111", title="[BACK] Algo"), capsys)


def test_create_title_must_start_with_the_epics_prefix(world, capsys):
    assert "epic's prefix [FRONT]" in problems(create_draft(title="Sem prefixo"), capsys)
    assert "epic's prefix [FRONT]" in problems(create_draft(title="[front] minúsculo"), capsys)
    assert "epic's prefix [FRONT]" in problems(create_draft(title="[BACK] Outro"), capsys)
    assert "epic's prefix [FRONT]" in problems(create_draft(title="[FRONT]sem espaço"), capsys)


def test_create_epic_without_prefix_accepts_any_title(world, capsys):
    passing(create_draft(epic="TS-110", title="Qualquer título"), capsys)


def test_create_title_length_limit(world, capsys):
    passing(create_draft(title="[FRONT] " + "a" * (255 - 8)), capsys)
    assert "256 characters" in problems(create_draft(title="[FRONT] " + "a" * (256 - 8)), capsys)


def test_create_requires_both_sections_with_content(world, capsys):
    assert "'## Contexto' section" in problems(
        create_draft(body="## Pronto quando\n- ok\n"), capsys
    )
    assert "'## Pronto quando' section" in problems(
        create_draft(body="## Contexto\nalgo\n"), capsys
    )
    assert "'## Contexto' is empty" in problems(
        create_draft(body="## Contexto\n\n## Pronto quando\n- ok\n"), capsys
    )
    assert "'## Pronto quando' is empty" in problems(
        create_draft(body="## Contexto\nalgo\n\n## Pronto quando\n"), capsys
    )
    assert "'## Contexto' section" in problems(
        create_draft(body="### Contexto\nalgo\n\n## Pronto quando\n- ok\n"), capsys
    )
    assert "more than once" in problems(
        create_draft(body=SECTIONS + "\n## Contexto\nde novo\n"), capsys
    )


def test_create_optional_sections_are_not_required(world, capsys):
    passing(create_draft(body=SECTIONS + "\n## Desenho combinado\nx\n"), capsys)


def test_create_description_that_cannot_convert_is_a_problem(world, capsys):
    body = SECTIONS + "\n| a | b |\n"

    assert "table" in problems(create_draft(body=body), capsys)


def test_create_priority_must_be_allowed(world, capsys):
    passing(create_draft(priority="Medium"), capsys)
    message = problems(create_draft(priority="Urgent"), capsys)
    assert "'Urgent' is not allowed" in message and "High, Medium" in message


def test_create_dates(world, capsys):
    assert "after due" in problems(create_draft(start=date(2026, 11, 2)), capsys)
    passing(create_draft(start=date(2026, 10, 31)), capsys)
    assert "before today" in problems(create_draft(due=date(2026, 10, 26), start=None), capsys)
    passing(create_draft(due=date(2026, 10, 27), start=None), capsys)


def test_create_needs_exactly_one_active_sprint(world, capsys):
    world.set_sprints([])
    assert "exactly one active sprint, found 0" in problems(create_draft(), capsys)
    world.set_sprints([{"id": 1, "name": "A"}, {"id": 2, "name": "B"}])
    assert "found 2 (A, B)" in problems(create_draft(), capsys)


def test_create_warns_when_the_active_sprint_ended(world, capsys):
    world.set_sprints([{"id": 55, "name": "Sprint 55", "endDate": "2026-10-01T15:00:00.000Z"}])

    code, verdict = check(create_draft(), capsys)

    assert code == 0
    assert "ended on 2026-10-01" in verdict["warnings"][0]


def test_today_comes_from_the_jira_time_zone_not_the_machine(world, capsys, monkeypatch):
    monkeypatch.setattr(card, "_now", lambda: datetime(2026, 10, 28, 1, 30, tzinfo=UTC))

    verdict = passing(create_draft(due=date(2026, 10, 27), start=None), capsys)

    assert verdict["resolved"]["today"] == "2026-10-27"
    assert verdict["requests"][0]["body"]["fields"][START_FIELD] == "2026-10-27"

    world.set_myself("Asia/Tokyo")
    assert "before today" in problems(create_draft(due=date(2026, 10, 27), start=None), capsys)


def test_invalid_time_zone_from_jira_is_exit_3(world, capsys):
    world.set_myself("Not/AZone")

    assert main(["card", "check", str(create_draft())]) == 3
    assert "time zone" in capsys.readouterr().err


def test_edit_changes_only_the_fields_that_differ(world, capsys):
    path = make_draft(
        "edit.md",
        "edit",
        key="TS-101",
        title="[FRONT] Novo título",
        priority="Medium",
        due=date(2026, 11, 6),
    )

    verdict = passing(path, capsys)

    assert verdict["requests"] == [
        {
            "method": "PUT",
            "path": "/rest/api/3/issue/TS-101",
            "body": {"fields": {"summary": "[FRONT] Novo título", "duedate": "2026-11-06"}},
        }
    ]


def test_edit_start_epic_and_description(world, capsys):
    path = make_draft(
        "edit.md",
        "edit",
        "## Contexto\nNovo.\n\n## Pronto quando\n- ok\n",
        key="TS-101",
        epic="TS-111",
        start=date(2026, 10, 27),
        title="[BACK] Tela",
    )

    verdict = passing(path, capsys)

    fields = verdict["requests"][0]["body"]["fields"]
    assert fields["parent"] == {"key": "TS-111"}
    assert fields[START_FIELD] == "2026-10-27"
    assert fields["description"] == to_adf("## Contexto\nNovo.\n\n## Pronto quando\n- ok\n")


def test_edit_with_nothing_to_change_is_a_problem(world, capsys):
    path = make_draft("edit.md", "edit", key="TS-101", priority="Medium")

    assert "changes nothing" in problems(path, capsys)


def test_edit_title_prefix_follows_the_current_or_the_new_epic(world, capsys):
    path = make_draft("e1.md", "edit", key="TS-101", title="[BACK] Errado")
    assert "epic's prefix [FRONT]" in problems(path, capsys)
    path = make_draft("e2.md", "edit", key="TS-101", title="[BACK] Certo", epic="TS-111")
    passing(path, capsys)
    path = make_draft("e3.md", "edit", key="TS-101", title="[FRONT] Errado", epic="TS-111")
    assert "epic's prefix [BACK]" in problems(path, capsys)
    path = make_draft("e4.md", "edit", key="TS-101", epic="TS-111")
    assert "epic's prefix [BACK]" in problems(path, capsys)


def test_edit_new_epic_follows_the_epic_rules(world, capsys):
    path = make_draft("e.md", "edit", key="TS-101", epic="TS-121")
    assert "is done" in problems(path, capsys)


def test_edit_dates_are_merged_with_the_current_ones(world, capsys):
    path = make_draft("e1.md", "edit", key="TS-101", start=date(2026, 11, 6))
    assert "start 2026-11-06 is after due 2026-11-05" in problems(path, capsys)
    path = make_draft("e2.md", "edit", key="TS-101", due=date(2026, 10, 25))
    assert "after due" in problems(path, capsys)
    path = make_draft("e3.md", "edit", key="TS-101", start=date(2026, 11, 5))
    passing(path, capsys)


def test_edit_priority_must_be_allowed(world, capsys):
    path = make_draft("e.md", "edit", key="TS-101", priority="Urgent")

    assert "'Urgent' is not allowed" in problems(path, capsys)


def test_edit_new_description_needs_the_sections(world, capsys):
    path = make_draft("e.md", "edit", "## Contexto\nsó isso\n", key="TS-101")

    assert "'## Pronto quando' section" in problems(path, capsys)


def test_edit_refuses_to_rewrite_a_description_it_cannot_write_back(world, capsys):
    table = {
        "type": "doc",
        "version": 1,
        "content": [
            {"type": "table", "content": []},
            {"type": "paragraph", "content": [{"type": "mention", "attrs": {"id": "x"}}]},
        ],
    }
    world.set_card("TS-101", description=table)
    path = make_draft("e.md", "edit", SECTIONS, key="TS-101")

    message = problems(path, capsys)

    assert "mention" in message and "table" in message


def test_edit_description_without_foreign_content_is_rewritten(world, capsys):
    world.set_card("TS-101", description=None)
    path = make_draft("e.md", "edit", SECTIONS, key="TS-101")

    verdict = passing(path, capsys)

    assert verdict["requests"][0]["body"]["fields"] == {"description": to_adf(SECTIONS)}


def test_move_matches_the_status_without_case_or_accents(world, capsys):
    for index, target in enumerate(["em validação", "EM VALIDACAO", "Em  Validação"]):
        path = make_draft(f"m{index}.md", "move", key="TS-101", to=target)
        verdict = passing(path, capsys)
        assert verdict["requests"] == [
            {
                "method": "POST",
                "path": "/rest/api/3/issue/TS-101/transitions",
                "body": {"transition": {"id": "31"}},
            }
        ]


def test_move_two_matches_are_refused_and_listed(world, capsys):
    world.set_transitions(
        "TS-101",
        [
            {"id": "31", "name": "Validar", "to": {"name": "Em Validação"}, "fields": {}},
            {"id": "32", "name": "Revalidar", "to": {"name": "Em validação"}, "fields": {}},
        ],
    )

    message = problems(make_draft("m.md", "move", key="TS-101", to="em validacao"), capsys)

    assert (
        "more than one" in message
        and "Validar (id 31)" in message
        and "Revalidar (id 32)" in message
    )


def test_move_without_a_matching_transition_lists_the_available_ones(world, capsys):
    message = problems(make_draft("m.md", "move", key="TS-101", to="Arquivado"), capsys)

    assert "no available transition" in message and "Em Validação" in message


def test_move_with_required_fields_is_refused(world, capsys):
    message = problems(make_draft("m.md", "move", key="TS-101", to="done"), capsys)

    assert "requires fields (Resolution)" in message and "by hand" in message


def test_move_optional_fields_do_not_block(world, capsys):
    world.set_transitions(
        "TS-101",
        [
            {
                "id": "31",
                "name": "Validar",
                "to": {"name": "Em Validação"},
                "fields": {"comment": {"required": False, "name": "Comment"}},
            }
        ],
    )

    passing(make_draft("m.md", "move", key="TS-101", to="Em Validação"), capsys)


def test_move_has_no_body(world, capsys):
    path = make_draft("m.md", "move", "texto\n", key="TS-101", to="Em Validação")

    assert "no body" in problems(path, capsys)


def test_comment_converts_the_body(world, capsys):
    verdict = passing(make_draft("c.md", "comment", "Feito **hoje**.\n", key="TS-101"), capsys)

    assert verdict["requests"] == [
        {
            "method": "POST",
            "path": "/rest/api/3/issue/TS-101/comment",
            "body": {"body": to_adf("Feito **hoje**.\n")},
        }
    ]


def test_comment_with_empty_or_unconvertible_body_is_a_problem(world, capsys):
    assert "empty" in problems(make_draft("c1.md", "comment", "\n\n", key="TS-101"), capsys)
    assert "table" in problems(make_draft("c2.md", "comment", "| a |\n", key="TS-101"), capsys)


@pytest.mark.parametrize("spent", ["2h", "30m", "1h 30m", "10h  5m"])
def test_worklog_time_format_passes(world, capsys, spent):
    verdict = passing(make_draft("w.md", "worklog", key="TS-101", time=spent), capsys)

    assert verdict["requests"][0]["body"]["timeSpent"] == " ".join(spent.split())


@pytest.mark.parametrize(
    "spent", ["2", "1.5h", "2 h", "1d", "h", "30m 1h 5m", "0h", "1h 1h", "2h30"]
)
def test_worklog_time_format_fails(world, capsys, spent):
    path = make_draft("w.md", "worklog", key="TS-101", time=spent)

    assert "time" in problems(path, capsys)


def test_worklog_start_is_nine_in_the_users_zone_without_a_colon_in_the_offset(world, capsys):
    path = make_draft(
        "w.md", "worklog", "Revisão.\n", key="TS-101", time="2h", day=date(2026, 10, 26)
    )

    verdict = passing(path, capsys)

    assert verdict["requests"] == [
        {
            "method": "POST",
            "path": "/rest/api/3/issue/TS-101/worklog",
            "body": {
                "timeSpent": "2h",
                "started": "2026-10-26T09:00:00.000-0300",
                "comment": to_adf("Revisão.\n"),
            },
        }
    ]


def test_worklog_day_defaults_to_today_and_cannot_be_after_it(world, capsys, monkeypatch):
    monkeypatch.setattr(card, "_now", lambda: datetime(2026, 10, 28, 1, 30, tzinfo=UTC))
    verdict = passing(make_draft("w1.md", "worklog", key="TS-101", time="1h"), capsys)
    assert verdict["requests"][0]["body"]["started"] == "2026-10-27T09:00:00.000-0300"
    assert "comment" not in verdict["requests"][0]["body"]

    path = make_draft("w2.md", "worklog", key="TS-101", time="1h", day=date(2026, 10, 28))
    assert "after today" in problems(path, capsys)


def test_worklog_offset_follows_the_zone(world, capsys):
    world.set_myself("Asia/Tokyo")

    verdict = passing(make_draft("w.md", "worklog", key="TS-101", time="1h"), capsys)

    assert verdict["requests"][0]["body"]["started"] == "2026-10-28T09:00:00.000+0900"


OPS = {
    "edit": lambda key: make_draft("o.md", "edit", key=key, priority="High"),
    "move": lambda key: make_draft("o.md", "move", key=key, to="Em Validação"),
    "comment": lambda key: make_draft("o.md", "comment", "Oi.\n", key=key),
    "worklog": lambda key: make_draft("o.md", "worklog", key=key, time="1h"),
}


@pytest.mark.parametrize("op", sorted(OPS))
@pytest.mark.parametrize("key", ["TS-102", "TS-103"])
def test_another_persons_or_unassigned_card_is_refused_for_every_op(world, capsys, op, key):
    world.set_transitions(key, [{"id": "31", "to": {"name": "Em Validação"}, "fields": {}}])

    assert "not assigned to you" in problems(OPS[op](key), capsys)
    assert world.writes() == []


@pytest.mark.parametrize("op", sorted(OPS))
@pytest.mark.parametrize("key", ["INFRA-5", "ts-101", "TS-101/x", "TS-0"])
def test_another_projects_key_is_refused_for_every_op_without_reading_it(world, capsys, op, key):
    before = len(world.fake.requests)
    path = OPS[op](key)

    assert "not a card of project TS" in problems(path, capsys)
    issue_reads = [
        r for r in world.fake.requests[before:] if r["path"].startswith("/rest/api/3/issue/")
    ]
    assert issue_reads == []


def test_card_of_another_project_found_by_key_is_refused(world, capsys):
    world.fake.routes[("GET", "/rest/api/3/issue/TS-140")] = (
        200,
        json.dumps({"key": "TS-140", "fields": {**_fields("x"), "project": {"key": "OTHER"}}}),
    )

    assert "does not belong to project TS" in problems(OPS["comment"]("TS-140"), capsys)


def test_card_not_found_is_a_problem(world, capsys):
    assert "was not found" in problems(OPS["comment"]("TS-999"), capsys)


def approve(path, code):
    return main(["card", "apply", str(path), "--approve", code])


def dry_run(path, capsys):
    code = main(["card", "apply", str(path), "--dry-run"])
    out = capsys.readouterr().out
    assert code == 0, out
    marker = "Código de aprovação: "
    return out, out.split(marker)[1].split()[0]


def pending_files():
    folder = data_dir() / "cards" / "pending"
    return sorted(folder.glob("*.json")) if folder.exists() else []


def test_dry_run_sends_no_write_and_stores_a_private_pending_record(world, capsys):
    path = create_draft()

    out, code = dry_run(path, capsys)

    assert world.writes() == []
    assert len(code) == 12 and set(code) <= set("0123456789abcdef")
    [record] = pending_files()
    assert record.name == f"{code}.json"
    assert stat.S_IMODE(record.stat().st_mode) == 0o600
    assert stat.S_IMODE(record.parent.stat().st_mode) == 0o700
    saved = json.loads(record.read_text())
    assert saved["requests"][0]["path"] == "/rest/api/3/issue"
    assert saved["drafts"][0]["sha256"]


def test_dry_run_preview_is_in_portuguese_and_shows_requests_without_credentials(world, capsys):
    out, code = dry_run(create_draft(), capsys)

    assert "Criar card no projeto TS" in out
    assert "Título: [FRONT] Título curto" in out
    assert "Sprint: Sprint 55 (termina em 2026-11-10)" in out
    assert "POST /rest/api/3/issue" in out
    assert "Authorization" not in out and "Basic" not in out and "sample-value" not in out


def test_dry_run_of_an_edit_shows_old_and_new_description(world, capsys):
    path = make_draft(
        "e.md", "edit", "## Contexto\nNovo texto.\n\n## Pronto quando\n- ok\n", key="TS-101"
    )

    out, _ = dry_run(path, capsys)

    assert "Descrição, antes:" in out and "Algo a explicar." in out
    assert "Descrição, depois:" in out and "Novo texto." in out


def test_dry_run_code_covers_site_methods_paths_and_bodies(world, capsys):
    _, first = dry_run(create_draft(), capsys)
    _, same = dry_run(create_draft(), capsys)
    _, other = dry_run(create_draft(priority="Medium"), capsys)

    assert first == same != other


def test_dry_run_with_a_problem_writes_no_record_and_exits_1(world, capsys):
    code = main(["card", "apply", str(create_draft(priority="Urgent")), "--dry-run"])

    assert code == 1
    assert "Urgent" in capsys.readouterr().out
    assert pending_files() == []


def test_apply_needs_exactly_one_of_the_flags(world, capsys):
    path = create_draft()

    assert main(["card", "apply", str(path)]) == 1
    assert main(["card", "apply", str(path), "--dry-run", "--approve", "abcdef012345"]) == 1
    assert world.fake.requests == []
    assert "--dry-run" in capsys.readouterr().err


def test_approve_without_a_pending_record_sends_nothing(world, capsys):
    path = create_draft()

    assert approve(path, "abcdef012345") == 1
    assert world.writes() == []
    assert "no pending" in capsys.readouterr().err


def test_approve_with_a_wrong_code_sends_nothing_and_keeps_the_record(world, capsys):
    path = create_draft()
    dry_run(path, capsys)

    assert approve(path, "abcdef012345") == 1
    assert world.writes() == []
    assert len(pending_files()) == 1


@pytest.mark.parametrize(
    "code", ["../../evil", "ABCDEF012345", "abc", "abcdef01234g", "", "abcdef012345\n"]
)
def test_approve_rejects_a_malformed_code_before_touching_the_disk(world, capsys, code):
    assert approve(create_draft(), code) == 1
    assert world.fake.requests == []
    assert "code" in capsys.readouterr().err


def test_approve_with_a_changed_draft_sends_nothing(world, capsys):
    path = create_draft()
    _, code = dry_run(path, capsys)
    path.write_text(path.read_text().replace("Título curto", "Título curtíssimo"))

    assert approve(path, code) == 1
    assert world.writes() == []
    assert "changed" in capsys.readouterr().err


def test_approve_expires_after_thirty_minutes(world, capsys, monkeypatch):
    path = create_draft()
    _, code = dry_run(path, capsys)
    monkeypatch.setattr(card, "_now", lambda: NOW + timedelta(minutes=31))

    assert approve(path, code) == 1
    assert world.writes() == []
    assert "expired" in capsys.readouterr().err

    monkeypatch.setattr(card, "_now", lambda: NOW + timedelta(minutes=29))
    _, code = dry_run(path, capsys)
    monkeypatch.setattr(card, "_now", lambda: NOW + timedelta(minutes=58))
    assert approve(path, code) == 0


def test_the_right_code_sends_exactly_the_previewed_requests_once(world, capsys):
    path = create_draft()
    _, code = dry_run(path, capsys)
    previewed = json.loads(pending_files()[0].read_text())["requests"]
    capsys.readouterr()

    assert approve(path, code) == 0

    [sent] = world.writes()
    assert {"method": sent["method"], "path": sent["path"], "body": sent["body"]} == previewed[0]
    assert sent["authorization"].startswith("Basic ")
    assert sent["content_type"] == "application/json"
    out = capsys.readouterr().out
    assert "TS-200" in out and f"{world.fake.site}/browse/TS-200" in out
    assert pending_files() == []
    assert not path.exists()
    assert (data_dir() / "cards" / "done" / "create.md").exists()


def test_a_second_approve_with_the_same_code_sends_nothing(world, capsys):
    path = create_draft()
    _, code = dry_run(path, capsys)
    assert approve(path, code) == 0
    count = len(world.writes())
    path = create_draft()

    assert approve(path, code) == 1
    assert len(world.writes()) == count


def test_a_204_answer_is_success(world, capsys):
    path = make_draft("e.md", "edit", key="TS-101", priority="High")
    _, code = dry_run(path, capsys)

    assert approve(path, code) == 0
    assert world.writes()[0]["method"] == "PUT"


def test_approve_reruns_the_checks_and_refuses_a_card_reassigned_since_the_preview(world, capsys):
    path = make_draft("c.md", "comment", "Oi.\n", key="TS-101")
    _, code = dry_run(path, capsys)
    world.set_card("TS-101", assignee="acc-other")

    assert approve(path, code) == 1
    assert world.writes() == []
    captured = capsys.readouterr()
    assert "not assigned to you" in captured.out + captured.err


def test_approve_refuses_when_the_requests_now_differ(world, capsys):
    path = create_draft()
    _, code = dry_run(path, capsys)
    world.set_sprints([{"id": 56, "name": "Sprint 56", "endDate": "2026-11-20T15:00:00.000Z"}])

    assert approve(path, code) == 1
    assert world.writes() == []
    assert "differ" in capsys.readouterr().err
    assert len(pending_files()) == 1


def test_approve_refuses_a_transition_that_disappeared(world, capsys):
    path = make_draft("m.md", "move", key="TS-101", to="Em Validação")
    _, code = dry_run(path, capsys)
    world.set_transitions("TS-101", [])

    assert approve(path, code) == 1
    assert world.writes() == []


def test_the_pending_record_is_deleted_before_anything_is_sent(world, capsys):
    path = create_draft()
    _, code = dry_run(path, capsys)
    seen = []
    original = card._send

    def spy(client, request):
        seen.append(len(pending_files()))
        return original(client, request)

    card._send = spy
    try:
        assert approve(path, code) == 0
    finally:
        card._send = original
    assert seen == [0]


def test_a_5xx_is_an_uncertain_result_with_no_retry_and_a_jql_for_create(world, capsys):
    world.fake.routes[("POST", "/rest/api/3/issue")] = (502, '{"errorMessages": ["bad gateway"]}')
    path = create_draft(title='[FRONT] Título "com aspas"')
    _, code = dry_run(path, capsys)
    capsys.readouterr()

    assert approve(path, code) == 3

    out = capsys.readouterr().out
    assert "resultado incerto: confira no Jira" in out
    assert 'summary ~ "\\"[FRONT] Título \\\\\\"com aspas\\\\\\"\\""' in out
    assert len(world.writes()) == 1
    assert pending_files() == []
    assert path.exists()


def test_a_connection_error_after_sending_is_uncertain(world, capsys, monkeypatch):
    path = make_draft("c.md", "comment", "Oi.\n", key="TS-101")
    _, code = dry_run(path, capsys)
    world.fake.write_delay = 3
    monkeypatch.setattr(card, "REQUEST_TIMEOUT", 1)
    capsys.readouterr()

    assert approve(path, code) == 3

    assert "resultado incerto" in capsys.readouterr().out
    assert len(world.requests_to("POST", "/rest/api/3/issue/TS-101/comment")) == 1


def test_jira_refusing_a_write_reports_its_message_and_exit_3(world, capsys):
    world.fake.routes[("PUT", "/rest/api/3/issue/TS-101")] = (
        400,
        json.dumps({"errors": {"duedate": "invalid"}}),
    )
    path = make_draft("e.md", "edit", key="TS-101", priority="High")
    _, code = dry_run(path, capsys)
    capsys.readouterr()

    assert approve(path, code) == 3

    captured = capsys.readouterr()
    assert "duedate: invalid" in captured.out + captured.err
    assert "resultado incerto" not in captured.out
    assert path.exists()


def folder_with_three():
    drafts = data_dir() / "cards" / "drafts"
    make_draft("1-comment.md", "comment", "Primeiro.\n", key="TS-101")
    make_draft("2-edit.md", "edit", key="TS-101", priority="High")
    make_draft("3-worklog.md", "worklog", key="TS-101", time="1h")
    return drafts


def test_a_folder_is_one_dry_run_and_one_approval_in_name_order(world, capsys):
    drafts = folder_with_three()
    _, code = dry_run(drafts, capsys)
    assert world.writes() == []

    assert approve(drafts, code) == 0

    assert [(r["method"], r["path"].rsplit("/", 1)[1]) for r in world.writes()] == [
        ("POST", "comment"),
        ("PUT", "TS-101"),
        ("POST", "worklog"),
    ]
    assert sorted(p.name for p in (data_dir() / "cards" / "done").iterdir()) == [
        "1-comment.md",
        "2-edit.md",
        "3-worklog.md",
    ]
    assert list(drafts.iterdir()) == []


def test_a_batch_stops_at_the_first_failure_and_reports_what_was_applied(world, capsys):
    drafts = folder_with_three()
    world.fake.routes[("PUT", "/rest/api/3/issue/TS-101")] = (
        400,
        json.dumps({"errorMessages": ["nope"]}),
    )
    _, code = dry_run(drafts, capsys)
    capsys.readouterr()

    assert approve(drafts, code) == 3

    out = capsys.readouterr()
    text = out.out + out.err
    assert [r["path"].rsplit("/", 1)[1] for r in world.writes()] == ["comment", "TS-101"]
    assert "1-comment.md" in text.split("2-edit.md")[0]
    assert "nope" in text
    assert "3-worklog.md" in text
    assert sorted(p.name for p in drafts.iterdir()) == ["2-edit.md", "3-worklog.md"]
    assert [p.name for p in (data_dir() / "cards" / "done").iterdir()] == ["1-comment.md"]


def test_a_batch_with_one_bad_draft_previews_nothing(world, capsys):
    drafts = folder_with_three()
    make_draft("4-bad.md", "comment", "Oi.\n", key="TS-102")

    assert main(["card", "apply", str(drafts), "--dry-run"]) == 1

    assert "4-bad.md" in capsys.readouterr().out
    assert pending_files() == []


def test_a_draft_added_to_the_folder_after_the_preview_is_refused(world, capsys):
    drafts = folder_with_three()
    _, code = dry_run(drafts, capsys)
    make_draft("4-more.md", "comment", "Extra.\n", key="TS-101")

    assert approve(drafts, code) == 1
    assert world.writes() == []


def test_the_pending_record_of_a_failed_approval_is_not_reusable(world, capsys):
    path = make_draft("c.md", "comment", "Oi.\n", key="TS-101")
    world.fake.routes[("POST", "/rest/api/3/issue/TS-101/comment")] = (500, "{}")
    _, code = dry_run(path, capsys)
    assert approve(path, code) == 3
    count = len(world.writes())

    assert approve(path, code) == 1
    assert len(world.writes()) == count


def test_apply_of_an_empty_folder_is_a_problem(world, capsys):
    folder = data_dir() / "cards" / "drafts"
    folder.mkdir(parents=True)

    assert main(["card", "apply", str(folder), "--dry-run"]) == 1


def test_epics_lists_open_epics_of_my_open_cards(world, capsys):
    epic = {
        "key": "TS-100",
        "fields": {
            "summary": "[FRONT] Épico de exemplo",
            "status": {"name": "In Progress", "statusCategory": {"key": "indeterminate"}},
            "issuetype": {"hierarchyLevel": 1},
        },
    }
    done_epic = {
        "key": "TS-121",
        "fields": {
            "summary": "[FRONT] Feito",
            "status": {"name": "Done", "statusCategory": {"key": "done"}},
            "issuetype": {"hierarchyLevel": 1},
        },
    }
    not_epic = {
        "key": "TS-120",
        "fields": {
            "summary": "Tarefa pai",
            "status": {"name": "To Do", "statusCategory": {"key": "new"}},
            "issuetype": {"hierarchyLevel": 0},
        },
    }
    no_prefix = {
        "key": "TS-110",
        "fields": {
            "summary": "Sem prefixo",
            "status": {"name": "To Do", "statusCategory": {"key": "new"}},
            "issuetype": {"hierarchyLevel": 1},
        },
    }
    issues = [
        {"key": f"TS-{n}", "fields": {"parent": parent}}
        for n, parent in enumerate([epic, epic, done_epic, not_epic, no_prefix, None], start=1)
    ]
    world.fake.pages = {None: {"issues": issues, "isLast": True}}

    assert main(["card", "epics"]) == 0

    assert json.loads(capsys.readouterr().out) == {
        "epics": [
            {
                "key": "TS-100",
                "title": "[FRONT] Épico de exemplo",
                "prefix": "[FRONT]",
                "status": "In Progress",
            },
            {"key": "TS-110", "title": "Sem prefixo", "prefix": None, "status": "To Do"},
        ]
    }
    search = world.requests_to("GET", "/rest/api/3/search/jql")[0]["query"]
    assert search["jql"] == (
        'assignee = currentUser() AND project = "TS" AND statusCategory != Done'
    )
    assert "parent" in search["fields"]


def test_epics_with_none_prints_an_empty_list(world, capsys):
    world.fake.pages = {None: {"issues": [], "isLast": True}}

    assert main(["card", "epics"]) == 0
    assert json.loads(capsys.readouterr().out) == {"epics": []}


@pytest.mark.parametrize("command", [["check"], ["epics"], ["apply", "--dry-run"]])
def test_missing_config_keys_exit_2_naming_them(world, capsys, command, ws_config):
    (ws_config / "config.toml").write_text(
        f'[jira]\nsite = "{world.fake.site}"\nemail = "{EMAIL}"\n', encoding="utf-8"
    )
    argv = ["card", command[0]]
    if command[0] != "epics":
        argv.append(str(create_draft()))
    argv += command[1:]

    assert main(argv) == 2

    err = capsys.readouterr().err
    assert "project" in err and "Local config" in err
    assert world.fake.requests == []


def test_create_needs_all_keys_but_a_comment_needs_only_the_project(world, capsys, ws_config):
    (ws_config / "config.toml").write_text(
        f'[jira]\nsite = "{world.fake.site}"\nemail = "{EMAIL}"\nproject = "TS"\n', encoding="utf-8"
    )

    assert main(["card", "check", str(create_draft())]) == 2
    err = capsys.readouterr().err
    for name in ["board_id", "issue_type", "start_date_field", "sprint_field"]:
        assert name in err
    capsys.readouterr()
    assert main(["card", "check", str(OPS["comment"]("TS-101"))]) == 0


def test_no_token_exits_2(world, capsys, ws_config):
    (ws_config / "credentials").unlink()

    assert main(["card", "check", str(create_draft())]) == 2
    assert "ws config token jira" in capsys.readouterr().err


def test_jira_401_exits_3(world, capsys):
    world.fake.status = 401
    world.fake.routes.clear()

    assert main(["card", "check", str(create_draft())]) == 3
    assert "401" in capsys.readouterr().err


def test_check_takes_one_draft_not_a_folder(world, capsys):
    folder = data_dir() / "cards" / "drafts"
    folder.mkdir(parents=True)

    assert main(["card", "check", str(folder)]) == 1


def test_check_of_a_bad_draft_prints_the_problems(world, capsys):
    path = make_draft("m.md", "move", key="TS-101", to="X", extra="y")

    assert "unknown key 'extra'" in problems(path, capsys)


def test_check_of_a_missing_file_is_a_problem(world, capsys):
    assert main(["card", "check", str(data_dir() / "nope.md")]) == 1


def test_the_store_is_private(world, capsys):
    dry_run(create_draft(), capsys)

    for name in ["", "pending", "done", "drafts"]:
        mode = os.stat(data_dir() / "cards" / name).st_mode
        assert stat.S_IMODE(mode) == 0o700


def test_check_creates_the_private_store_and_writes_nothing(world, capsys):
    passing(create_draft(), capsys)

    assert world.writes() == []
    assert Path(data_dir() / "cards" / "pending").exists()


def test_guard_allows_only_the_five_shapes_on_cards_of_the_project():
    good = [
        {"method": "POST", "path": "/rest/api/3/issue"},
        {"method": "PUT", "path": "/rest/api/3/issue/TS-1"},
        {"method": "POST", "path": "/rest/api/3/issue/TS-1/transitions"},
        {"method": "POST", "path": "/rest/api/3/issue/TS-1/comment"},
        {"method": "POST", "path": "/rest/api/3/issue/TS-1/worklog"},
    ]
    assert card.guard("TS", good) is None
    for method, path in [
        ("DELETE", "/rest/api/3/issue/TS-1"),
        ("PUT", "/rest/api/3/issue/OTHER-1"),
        ("POST", "/rest/api/3/issue/TS-1/assignee"),
        ("PUT", "/rest/api/3/issue/TS-1/comment"),
        ("POST", "/rest/api/3/issue/TS-1/worklog/9"),
        ("POST", "/rest/api/3/issue/TS-1/../TS-2"),
    ]:
        assert card.guard("TS", [{"method": method, "path": path}]) == f"{method} {path}"


def read_record():
    [path] = pending_files()
    return path, json.loads(path.read_text())


def test_a_cosmetic_change_to_a_draft_after_the_preview_is_refused(world, capsys):
    path = make_draft("m.md", "move", key="TS-101", to="Em Validação")
    _, code = dry_run(path, capsys)
    path.write_text(path.read_text() + "\n  \n")

    assert approve(path, code) == 1

    assert "changed" in capsys.readouterr().err
    assert world.writes() == []
    assert len(pending_files()) == 1


def test_a_renamed_draft_or_a_copy_elsewhere_is_refused_even_with_the_same_requests(world, capsys):
    drafts = data_dir() / "cards" / "drafts"
    make_draft("a.md", "move", key="TS-101", to="Em Validação")
    _, code = dry_run(drafts, capsys)
    (drafts / "a.md").rename(drafts / "b.md")

    assert approve(drafts, code) == 1
    assert "changed" in capsys.readouterr().err
    assert world.writes() == []

    (drafts / "b.md").rename(drafts / "a.md")
    copy = drafts / "sub" / "a.md"
    copy.parent.mkdir()
    copy.write_text((drafts / "a.md").read_text())
    assert approve(copy, code) == 1
    assert world.writes() == []


def test_a_malformed_code_never_reads_a_file_outside_the_pending_folder(world, capsys):
    card._ensure_store()
    planted = data_dir() / "cards" / "x.json"
    old = (NOW - timedelta(hours=2)).isoformat()
    planted.write_text(json.dumps({"created_at": old}))
    planted.chmod(0o600)

    assert approve(create_draft(), "../x") == 1

    assert planted.exists()
    assert json.loads(planted.read_text()) == {"created_at": old}
    assert world.fake.requests == []


def test_the_code_changes_with_the_path_the_site_and_the_before_state():
    request = {"method": "PUT", "path": "/rest/api/3/issue/TS-1", "body": {"fields": {"a": 1}}}
    base = card.approval_code("https://example.atlassian.net", [request], [{}])

    assert base == card.approval_code("https://example.atlassian.net/", [request], [{}])
    other_key = {**request, "path": "/rest/api/3/issue/TS-2"}
    assert card.approval_code("https://example.atlassian.net", [other_key], [{}]) != base
    assert card.approval_code("https://other.atlassian.net", [request], [{}]) != base
    other_method = {**request, "method": "POST"}
    assert card.approval_code("https://example.atlassian.net", [other_method], [{}]) != base
    other_body = {**request, "body": {"fields": {"a": 2}}}
    assert card.approval_code("https://example.atlassian.net", [other_body], [{}]) != base
    assert card.approval_code("https://example.atlassian.net", [request], [{"a": 1}]) != base


def test_a_pending_record_for_another_site_is_refused(world, capsys):
    path = make_draft("c.md", "comment", "Oi.\n", key="TS-101")
    _, code = dry_run(path, capsys)
    record_path, record = read_record()
    record["site"] = "https://other.atlassian.net"
    record_path.write_text(json.dumps(record))

    assert approve(path, code) == 1

    assert "differ" in capsys.readouterr().err
    assert world.writes() == []
    assert record_path.exists()


def test_a_draft_outside_the_drafts_folder_is_refused_everywhere(world, capsys, tmp_path):
    outside = tmp_path / "elsewhere.md"
    outside.write_text(create_draft().read_text())

    assert main(["card", "check", str(outside)]) == 1
    assert "inside" in capsys.readouterr().out
    assert main(["card", "apply", str(outside), "--dry-run"]) == 1
    assert main(["card", "apply", str(tmp_path), "--dry-run"]) == 1
    assert main(["card", "apply", str(outside), "--approve", "abcdef012345"]) == 1
    assert world.fake.requests == []
    assert pending_files() == []


def test_a_symlink_that_leaves_the_drafts_folder_is_refused(world, capsys, tmp_path):
    drafts = data_dir() / "cards" / "drafts"
    drafts.mkdir(parents=True, exist_ok=True)
    outside = tmp_path / "secret.md"
    outside.write_text(create_draft().read_text())
    (drafts / "link.md").symlink_to(outside)

    assert main(["card", "check", str(drafts / "link.md")]) == 1
    assert main(["card", "apply", str(drafts), "--dry-run"]) == 1
    assert "symlink" in capsys.readouterr().err
    assert main(["card", "apply", str(drafts / "link.md"), "--dry-run"]) == 1
    folder_link = data_dir() / "cards" / "linked"
    folder_link.symlink_to(tmp_path)
    assert main(["card", "apply", str(folder_link), "--dry-run"]) == 1
    assert world.fake.requests == []
    assert outside.exists()


def test_a_symlink_inside_the_drafts_folder_is_also_refused(world, capsys):
    drafts = data_dir() / "cards" / "drafts"
    real = make_draft("real.md", "comment", "Oi.\n", key="TS-101")
    (drafts / "alias.md").symlink_to(real)

    assert main(["card", "apply", str(drafts), "--dry-run"]) == 1
    assert main(["card", "check", str(drafts / "alias.md")]) == 1


def test_only_files_inside_the_drafts_folder_are_moved_to_done(world, tmp_path):
    card._ensure_store()
    outside = tmp_path / "keep.md"
    outside.write_text("x")

    with pytest.raises(OSError, match="not inside"):
        card._move_to_done(outside)

    assert outside.exists()
    assert list((data_dir() / "cards" / "done").iterdir()) == []


def test_an_edit_is_refused_when_the_card_changed_since_the_preview(world, capsys):
    path = make_draft("e.md", "edit", key="TS-101", title="[FRONT] Novo título")
    _, code = dry_run(path, capsys)
    world.set_card("TS-101", fields={"summary": "[FRONT] Alguém mexeu"})

    assert approve(path, code) == 1

    assert "o card mudou no Jira desde a prévia; rode o --dry-run de novo" in (
        capsys.readouterr().err
    )
    assert world.writes() == []


@pytest.mark.parametrize(
    "draft, change",
    [
        (("priority", "High"), {"priority": {"name": "Low"}}),
        (("due", date(2026, 11, 20)), {"duedate": "2026-11-06"}),
        (("start", date(2026, 10, 27)), {START_FIELD: "2026-10-20"}),
    ],
)
def test_every_changed_field_is_covered_by_the_before_state(world, capsys, draft, change):
    path = make_draft("e.md", "edit", key="TS-101", **{draft[0]: draft[1]})
    _, code = dry_run(path, capsys)
    world.set_card("TS-101", fields=change)

    assert approve(path, code) == 1
    assert world.writes() == []


def test_an_edit_of_the_description_is_refused_when_the_old_text_changed(world, capsys):
    path = make_draft(
        "e.md", "edit", "## Contexto\nNovo.\n\n## Pronto quando\n- ok\n", key="TS-101"
    )
    _, code = dry_run(path, capsys)
    world.set_card("TS-101", description=to_adf(SECTIONS + "\nmais uma linha\n"))

    assert approve(path, code) == 1
    assert world.writes() == []


def test_an_edit_whose_card_did_not_change_is_still_approved(world, capsys):
    path = make_draft("e.md", "edit", key="TS-101", title="[FRONT] Novo título")
    _, code = dry_run(path, capsys)
    world.set_card("TS-101", fields={"duedate": "2026-12-01"})

    assert approve(path, code) == 0


def test_a_move_is_refused_when_the_status_changed_since_the_preview(world, capsys):
    path = make_draft("m.md", "move", key="TS-101", to="Em Validação")
    _, code = dry_run(path, capsys)
    status = {"name": "Blocked", "statusCategory": {"key": "indeterminate"}}
    world.set_card("TS-101", status=status)

    assert approve(path, code) == 1

    assert "o card mudou no Jira desde a prévia" in capsys.readouterr().err
    assert world.writes() == []


def test_a_pending_record_dated_in_the_future_is_refused(world, capsys, monkeypatch):
    path = make_draft("c.md", "comment", "Oi.\n", key="TS-101")
    _, code = dry_run(path, capsys)
    monkeypatch.setattr(card, "_now", lambda: NOW - timedelta(minutes=5))

    assert approve(path, code) == 1

    assert "future" in capsys.readouterr().err
    assert world.writes() == []


def test_a_pending_record_that_is_not_private_is_refused(world, capsys):
    path = make_draft("c.md", "comment", "Oi.\n", key="TS-101")
    _, code = dry_run(path, capsys)
    record_path, _ = read_record()
    record_path.chmod(0o644)

    assert approve(path, code) == 1
    assert "not a private file" in capsys.readouterr().err
    assert world.writes() == []


def test_a_pending_record_owned_by_someone_else_is_refused(world, capsys, monkeypatch):
    path = make_draft("c.md", "comment", "Oi.\n", key="TS-101")
    _, code = dry_run(path, capsys)
    monkeypatch.setattr(card.os, "getuid", lambda: os.stat(data_dir()).st_uid + 1)

    assert approve(path, code) == 1
    assert "not a private file" in capsys.readouterr().err
    assert world.writes() == []


def test_a_pending_record_that_is_a_symlink_is_refused(world, capsys, tmp_path):
    path = make_draft("c.md", "comment", "Oi.\n", key="TS-101")
    _, code = dry_run(path, capsys)
    record_path, _ = read_record()
    target = tmp_path / "real.json"
    record_path.rename(target)
    record_path.symlink_to(target)

    assert approve(path, code) == 1
    assert world.writes() == []


def test_a_day_rollover_between_preview_and_approve_says_so(world, capsys, monkeypatch):
    path = create_draft(start=None)
    monkeypatch.setattr(card, "_now", lambda: datetime(2026, 10, 28, 2, 50, tzinfo=UTC))
    _, code = dry_run(path, capsys)
    monkeypatch.setattr(card, "_now", lambda: datetime(2026, 10, 28, 3, 10, tzinfo=UTC))

    assert approve(path, code) == 1

    assert "a data de hoje mudou desde a prévia; rode o --dry-run de novo" in (
        capsys.readouterr().err
    )
    assert world.writes() == []


def test_a_day_rollover_does_not_matter_when_nothing_depends_on_today(world, capsys, monkeypatch):
    path = create_draft(start=date(2026, 10, 27))
    monkeypatch.setattr(card, "_now", lambda: datetime(2026, 10, 28, 2, 50, tzinfo=UTC))
    _, code = dry_run(path, capsys)
    monkeypatch.setattr(card, "_now", lambda: datetime(2026, 10, 28, 3, 10, tzinfo=UTC))

    assert approve(path, code) == 0


def test_the_printed_approve_command_is_shell_quoted(world, capsys):
    drafts = data_dir() / "cards" / "drafts"
    path = make_draft("a b; echo $x.md", "comment", "Oi.\n", key="TS-101")

    out, code = dry_run(path, capsys)

    assert f"ws card apply '{path}' --approve {code}" in out
    assert drafts.exists()


def test_a_pending_record_that_cannot_be_saved_is_a_clear_message(world, capsys, monkeypatch):
    original = os.open

    def deny(path, *args, **kwargs):
        if str(path).endswith(".json"):
            raise PermissionError(13, "Permission denied")
        return original(path, *args, **kwargs)

    monkeypatch.setattr(card.os, "open", deny)

    assert main(["card", "apply", str(create_draft()), "--dry-run"]) == 1

    captured = capsys.readouterr()
    assert "could not save the pending record" in captured.err
    assert "Código de aprovação" not in captured.out
    assert pending_files() == []


def test_an_unexpected_error_after_a_write_still_reports_it_and_lists_the_rest(
    world, capsys, monkeypatch
):
    drafts = folder_with_three()
    _, code = dry_run(drafts, capsys)
    capsys.readouterr()
    original = card._send
    calls = []

    def flaky(client, request):
        calls.append(request["path"])
        if len(calls) == 2:
            raise RuntimeError("boom")
        return original(client, request)

    monkeypatch.setattr(card, "_send", flaky)

    assert approve(drafts, code) == 3

    out = capsys.readouterr().out
    assert "Aplicado: 1-comment.md" in out
    assert "Já aplicados: 1-comment.md" in out
    assert "2-edit.md: resultado incerto" in out
    assert "Não enviados: 3-worklog.md" in out
    assert sorted(p.name for p in drafts.iterdir()) == ["2-edit.md", "3-worklog.md"]
    assert [p.name for p in (data_dir() / "cards" / "done").iterdir()] == ["1-comment.md"]


def test_a_failure_moving_an_applied_draft_does_not_hide_the_write(world, capsys, monkeypatch):
    drafts = folder_with_three()
    _, code = dry_run(drafts, capsys)
    capsys.readouterr()
    original = card._move_to_done

    def broken(path):
        if path.name.startswith("1-"):
            raise OSError("disk full")
        return original(path)

    monkeypatch.setattr(card, "_move_to_done", broken)

    assert approve(drafts, code) == 0

    out = capsys.readouterr().out
    assert "Aplicado, mas não consegui mover 1-comment.md" in out
    assert len(world.writes()) == 3


def test_an_odd_answer_to_a_write_does_not_turn_a_success_into_an_error(world, capsys):
    world.fake.routes[("POST", "/rest/api/3/issue")] = (201, "[]")
    path = create_draft()
    _, code = dry_run(path, capsys)
    capsys.readouterr()

    assert approve(path, code) == 0

    assert "Criado: create.md" in capsys.readouterr().out
    assert not path.exists()


def test_approve_stops_a_forged_request_shape_and_keeps_the_record(world, capsys, monkeypatch):
    forged = cardrules.Verdict(
        request={"method": "DELETE", "path": "/rest/api/3/issue/TS-101", "body": {}},
        preview=["forjado"],
        resolved={"today": "2026-10-27"},
    )
    monkeypatch.setattr(cardrules, "check", lambda context, draft: forged)
    path = make_draft("c.md", "comment", "Oi.\n", key="TS-101")
    _, code = dry_run(path, capsys)

    assert approve(path, code) == 1

    assert "outside the allowed shapes" in capsys.readouterr().err
    assert world.writes() == []
    assert len(pending_files()) == 1


def test_a_project_key_with_a_trailing_newline_is_a_setup_problem(world, capsys, ws_config):
    (ws_config / "config.toml").write_text(
        f'[jira]\nsite = "{world.fake.site}"\nemail = "{EMAIL}"\nproject = "TS\\n"\n'
        f'board_id = 7\nissue_type = "Tarefa"\nstart_date_field = "{START_FIELD}"\n'
        f'sprint_field = "{SPRINT_FIELD}"\n',
        encoding="utf-8",
    )

    assert main(["card", "check", str(create_draft())]) == 2
    assert "project" in capsys.readouterr().err
    assert world.fake.requests == []


def test_a_site_that_is_not_atlassian_cloud_exits_2_before_any_request(world, capsys, ws_config):
    for site in ["http://example.atlassian.net", "https://evil.example"]:
        (ws_config / "config.toml").write_text(
            f'[jira]\nsite = "{site}"\nemail = "{EMAIL}"\nproject = "TS"\n', encoding="utf-8"
        )

        assert main(["card", "check", str(OPS["comment"]("TS-101"))]) == 2
        assert "atlassian.net" in capsys.readouterr().err
    assert world.fake.requests == []


def test_approve_needs_the_ask_rule_and_the_hook_in_the_claude_settings(
    world, capsys, claude_settings
):
    path = make_draft("c.md", "comment", "Oi.\n", key="TS-101")
    _, code = dry_run(path, capsys)
    capsys.readouterr()
    before = len(world.fake.requests)

    write_claude_settings(claude_settings, ask=("Bash(other:*)",))
    assert approve(path, code) == 2
    assert "Bash(ws card apply:*)" in capsys.readouterr().err

    write_claude_settings(claude_settings, hook=False)
    assert approve(path, code) == 2
    assert "ask_card_apply.py" in capsys.readouterr().err

    claude_settings.unlink()
    assert approve(path, code) == 2
    assert "not found" in capsys.readouterr().err

    assert len(world.fake.requests) == before
    assert world.writes() == []
    assert len(pending_files()) == 1

    write_claude_settings(claude_settings)
    assert approve(path, code) == 0


def test_the_preview_does_not_need_the_claude_settings(world, capsys, claude_settings):
    claude_settings.unlink()

    dry_run(create_draft(), capsys)
