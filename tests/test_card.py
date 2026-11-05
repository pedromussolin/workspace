import itertools
import json
import os
import stat
import sys
from datetime import UTC, date, datetime, timedelta
from pathlib import Path

import pytest

from ws import card, cardrules, humans
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
                    "id": "21",
                    "name": "Iniciar",
                    "to": {"name": "Em Andamento", "statusCategory": {"key": "indeterminate"}},
                    "fields": {},
                },
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


REAL_SESSION_ID = card._session_id
REAL_INTERACTIVE = card._interactive
REAL_UNDER_HARNESS = humans.under_agent_harness


HOOKS_COPY = "/srv/claude/hooks/workspace"


def write_claude_settings(path, ask=("Bash(ws card apply:*)",), hook=True):
    gates = {"permissions": {"ask": list(ask)}}
    if hook:
        command = f'python3 -I "{HOOKS_COPY}/approval_gate.py"'
        entry = {"matcher": "Bash|mcp__.*", "hooks": [{"type": "command", "command": command}]}
        gates["hooks"] = {"PreToolUse": [entry]}
    path.write_text(json.dumps(gates), encoding="utf-8")


@pytest.fixture
def claude_settings(tmp_path, monkeypatch):
    path = tmp_path / "claude-settings.json"
    write_claude_settings(path)
    monkeypatch.setenv("WS_CLAUDE_SETTINGS", str(path))
    monkeypatch.setenv("WS_CLAUDE_HOOKS_DIR", HOOKS_COPY)
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
    sessions = itertools.count(1000)
    monkeypatch.setattr(card, "_session_id", lambda: next(sessions))
    monkeypatch.setattr(card, "_interactive", lambda: False)
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
    raw = b'+++\nop = "create"\nepic = "TS-1"\npriority = "High"\ndue = 2026-10-31\n+++\n# T\n\nx\n'

    draft = parse_draft(raw)

    assert draft.values["due"] == date(2026, 10, 31)
    assert draft.title == "T"


def test_draft_edit_still_accepts_a_start_date():
    raw = b'+++\nop = "edit"\nkey = "TS-1"\nstart = "2026-10-28"\n+++\n'

    assert parse_draft(raw).values["start"] == date(2026, 10, 28)


def test_draft_create_refuses_a_start_key():
    raw = (
        b'+++\nop = "create"\nepic = "TS-1"\npriority = "High"\n'
        b"due = 2026-10-31\nstart = 2026-10-28\n+++\n# T\n\nx\n"
    )

    with pytest.raises(DraftError, match="unknown key 'start' for op create"):
        parse_draft(raw)


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
    verdict = passing(create_draft(), capsys)

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
        "duedate": "2026-10-31",
        SPRINT_FIELD: 55,
    }
    assert world.writes() == []


def test_create_sends_no_start_date_and_the_preview_has_none(world, capsys):
    verdict = passing(create_draft(), capsys)

    assert START_FIELD not in verdict["requests"][0]["body"]["fields"]
    out, _ = preview(create_draft(), capsys)
    assert "Início" not in out and "Data de início" not in out


def test_create_with_a_start_key_is_refused_by_check(world, capsys):
    assert "unknown key 'start'" in problems(create_draft(start=date(2026, 10, 28)), capsys)


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
    assert "before today" in problems(create_draft(due=date(2026, 10, 26)), capsys)
    passing(create_draft(due=date(2026, 10, 27)), capsys)


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

    verdict = passing(create_draft(due=date(2026, 10, 27)), capsys)

    assert verdict["resolved"]["today"] == "2026-10-27"

    world.set_myself("Asia/Tokyo")
    assert "before today" in problems(create_draft(due=date(2026, 10, 27)), capsys)


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


def start_move(name="m.md"):
    return make_draft(name, "move", key="TS-101", to="Em Andamento")


def test_move_to_in_progress_with_no_start_date_adds_the_start_request(world, capsys):
    world.set_card("TS-101", **{START_FIELD: None})

    verdict = passing(start_move(), capsys)

    assert verdict["requests"] == [
        {
            "method": "POST",
            "path": "/rest/api/3/issue/TS-101/transitions",
            "body": {"transition": {"id": "21"}},
        },
        {
            "method": "PUT",
            "path": "/rest/api/3/issue/TS-101",
            "body": {"fields": {START_FIELD: "2026-10-27"}},
        },
    ]


def test_move_to_in_progress_with_a_start_date_sends_only_the_transition(world, capsys):
    verdict = passing(start_move(), capsys)

    assert [r["path"] for r in verdict["requests"]] == ["/rest/api/3/issue/TS-101/transitions"]


def test_move_to_another_status_never_adds_the_start_request(world, capsys):
    world.set_card("TS-101", **{START_FIELD: None})
    path = make_draft("m.md", "move", key="TS-101", to="Em Validação")

    verdict = passing(path, capsys)

    assert len(verdict["requests"]) == 1


def test_move_start_date_is_today_in_the_users_zone(world, capsys, monkeypatch):
    world.set_card("TS-101", **{START_FIELD: None})
    monkeypatch.setattr(card, "_now", lambda: datetime(2026, 10, 28, 1, 30, tzinfo=UTC))

    verdict = passing(start_move(), capsys)

    assert verdict["requests"][1]["body"] == {"fields": {START_FIELD: "2026-10-27"}}


def test_move_follows_the_status_overrides_for_in_progress(world, capsys, ws_config):
    config = ws_config / "config.toml"
    config.write_text(
        config.read_text() + '\n[jira.status_overrides]\n"Em Validação" = "in_progress"\n',
        encoding="utf-8",
    )
    world.set_card("TS-101", **{START_FIELD: None})
    path = make_draft("m.md", "move", key="TS-101", to="Em Validação")

    verdict = passing(path, capsys)

    assert [r["method"] for r in verdict["requests"]] == ["POST", "PUT"]


def test_move_override_can_take_an_in_progress_category_out(world, capsys, ws_config):
    config = ws_config / "config.toml"
    config.write_text(
        config.read_text() + '\n[jira.status_overrides]\n"Em Andamento" = "blocked"\n',
        encoding="utf-8",
    )
    world.set_card("TS-101", **{START_FIELD: None})

    verdict = passing(start_move(), capsys)

    assert len(verdict["requests"]) == 1


def test_move_with_a_due_date_in_the_past_warns_but_does_not_refuse(world, capsys):
    world.set_card("TS-101", duedate="2026-10-20", **{START_FIELD: None})

    verdict = passing(start_move(), capsys)

    assert len(verdict["requests"]) == 2
    assert any("2026-10-20" in warning and "start" in warning for warning in verdict["warnings"])


def test_move_with_a_due_date_today_or_later_has_no_warning(world, capsys):
    world.set_card("TS-101", duedate="2026-10-27", **{START_FIELD: None})

    assert passing(start_move(), capsys)["warnings"] == []


def test_move_preview_shows_the_start_date_and_both_requests(world, capsys):
    world.set_card("TS-101", **{START_FIELD: None})

    out, _ = preview(start_move(), capsys)

    assert "Data de início: hoje, 27/10" in out
    assert "POST /rest/api/3/issue/TS-101/transitions" in out
    assert "PUT /rest/api/3/issue/TS-101" in out


def test_move_preview_without_the_start_request_has_no_start_line(world, capsys):
    out, _ = preview(start_move(), capsys)

    assert "Data de início" not in out


def test_one_code_sends_the_transition_then_the_start_date_once(world, capsys):
    world.set_card("TS-101", **{START_FIELD: None})
    path = start_move()
    _, code = preview(path, capsys)
    capsys.readouterr()

    assert approve(path, code) == 0

    assert [(r["method"], r["path"]) for r in world.writes()] == [
        ("POST", "/rest/api/3/issue/TS-101/transitions"),
        ("PUT", "/rest/api/3/issue/TS-101"),
    ]
    assert world.writes()[1]["body"] == {"fields": {START_FIELD: "2026-10-27"}}
    assert "Aplicado: m.md" in capsys.readouterr().out
    assert (data_dir() / "cards" / "done" / "m.md").exists()
    assert approve(path, code) == 1
    assert len(world.writes()) == 2


def test_a_start_date_set_since_the_preview_refuses_the_move(world, capsys):
    world.set_card("TS-101", **{START_FIELD: None})
    path = start_move()
    _, code = preview(path, capsys)
    world.set_card("TS-101", **{START_FIELD: "2026-10-26"})

    assert approve(path, code) == 1
    assert world.writes() == []


def test_the_move_code_covers_the_current_start_date(world, capsys):
    _, with_date = preview(start_move(), capsys)
    world.set_card("TS-101", **{START_FIELD: "2026-10-20"})
    _, other_date = preview(start_move(), capsys)

    assert with_date != other_date


def test_a_failing_start_request_reports_the_transition_as_applied(world, capsys):
    world.set_card("TS-101", **{START_FIELD: None})
    world.fake.routes[("PUT", "/rest/api/3/issue/TS-101")] = (
        400,
        json.dumps({"errorMessages": ["nope"]}),
    )
    drafts = data_dir() / "cards" / "drafts"
    make_draft("1-comment.md", "comment", "Primeiro.\n", key="TS-101")
    make_draft("2-move.md", "move", key="TS-101", to="Em Andamento")
    make_draft("3-worklog.md", "worklog", key="TS-101", time="1h")
    _, code = preview(drafts, capsys)
    capsys.readouterr()

    assert approve(drafts, code) == 3

    out = capsys.readouterr()
    text = out.out + out.err
    assert [r["path"].rsplit("/", 1)[1] for r in world.writes()] == [
        "comment",
        "transitions",
        "TS-101",
    ]
    assert "Já aplicados: 1-comment.md" in text
    assert "2-move.md: a transição foi aplicada, mas a data de início não" in text
    assert "o Jira recusou" in text and "nope" in text
    assert "Não enviados: 3-worklog.md" in text
    assert [p.name for p in (data_dir() / "cards" / "uncertain").iterdir()] == ["2-move.md"]
    assert sorted(p.name for p in drafts.iterdir()) == ["3-worklog.md"]


def test_a_start_request_with_an_uncertain_result_follows_the_uncertain_rules(world, capsys):
    world.set_card("TS-101", **{START_FIELD: None})
    world.fake.routes[("PUT", "/rest/api/3/issue/TS-101")] = (500, "{}")
    path = start_move()
    _, code = preview(path, capsys)
    capsys.readouterr()

    assert approve(path, code) == 3

    text = capsys.readouterr().out
    assert "a transição foi aplicada, mas a data de início não" in text
    assert "m.md: resultado incerto" in text
    assert len(world.writes()) == 2
    assert [p.name for p in (data_dir() / "cards" / "uncertain").iterdir()] == ["m.md"]


def test_a_failing_transition_never_sends_the_start_request(world, capsys):
    world.set_card("TS-101", **{START_FIELD: None})
    world.fake.routes[("POST", "/rest/api/3/issue/TS-101/transitions")] = (
        400,
        json.dumps({"errorMessages": ["nope"]}),
    )
    path = start_move()
    _, code = preview(path, capsys)
    capsys.readouterr()

    assert approve(path, code) == 3

    assert [r["path"].rsplit("/", 1)[1] for r in world.writes()] == ["transitions"]
    assert "a transição foi aplicada" not in capsys.readouterr().out


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


def preview(path, capsys):
    code = main(["card", "preview", str(path)])
    out = capsys.readouterr().out
    assert code == 0, out
    marker = "Código de aprovação: "
    return out, out.split(marker)[1].split()[0]


def pending_files():
    folder = data_dir() / "cards" / "pending"
    return sorted(folder.glob("*.json")) if folder.exists() else []


def test_preview_sends_no_write_and_stores_a_private_pending_record(world, capsys):
    path = create_draft()

    out, code = preview(path, capsys)

    assert world.writes() == []
    assert len(code) == 12 and set(code) <= set("0123456789abcdef")
    [record] = pending_files()
    assert record.name == f"{code}.json"
    assert stat.S_IMODE(record.stat().st_mode) == 0o600
    assert stat.S_IMODE(record.parent.stat().st_mode) == 0o700
    saved = json.loads(record.read_text())
    assert saved["requests"][0]["path"] == "/rest/api/3/issue"
    assert saved["drafts"][0]["sha256"]


def test_preview_preview_is_in_portuguese_and_shows_requests_without_credentials(world, capsys):
    out, code = preview(create_draft(), capsys)

    assert "Criar card no projeto TS" in out
    assert "Título: [FRONT] Título curto" in out
    assert "Sprint: Sprint 55 (termina em 2026-11-10)" in out
    assert "POST /rest/api/3/issue" in out
    assert "Authorization" not in out and "Basic" not in out and "sample-value" not in out


def test_preview_of_an_edit_shows_old_and_new_description(world, capsys):
    path = make_draft(
        "e.md", "edit", "## Contexto\nNovo texto.\n\n## Pronto quando\n- ok\n", key="TS-101"
    )

    out, _ = preview(path, capsys)

    assert "Descrição, antes:" in out and "Algo a explicar." in out
    assert "Descrição, depois:" in out and "Novo texto." in out


def test_preview_code_covers_site_methods_paths_and_bodies(world, capsys):
    _, first = preview(create_draft(), capsys)
    _, same = preview(create_draft(), capsys)
    _, other = preview(create_draft(priority="Medium"), capsys)

    assert first == same != other


def test_preview_with_a_problem_writes_no_record_and_exits_1(world, capsys):
    code = main(["card", "preview", str(create_draft(priority="Urgent"))])

    assert code == 1
    assert "Urgent" in capsys.readouterr().out
    assert pending_files() == []


def test_apply_without_approve_is_an_error_and_there_is_no_dry_run_flag(world, capsys):
    path = create_draft()

    assert main(["card", "apply", str(path)]) == 1
    assert "--approve" in capsys.readouterr().err
    with pytest.raises(SystemExit):
        main(["card", "apply", str(path), "--dry-run"])
    assert world.fake.requests == []
    assert pending_files() == []


@pytest.mark.parametrize("flag", ["--appr", "--app", "--approv", "--a"])
def test_the_approve_flag_cannot_be_abbreviated(world, capsys, flag):
    path = create_draft()

    with pytest.raises(SystemExit):
        main(["card", "apply", str(path), flag, "abcdef012345"])

    assert world.fake.requests == []


def test_approve_without_a_pending_record_sends_nothing(world, capsys):
    path = create_draft()

    assert approve(path, "abcdef012345") == 1
    assert world.writes() == []
    assert "no pending" in capsys.readouterr().err


def test_approve_with_a_wrong_code_sends_nothing_and_keeps_the_record(world, capsys):
    path = create_draft()
    preview(path, capsys)

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
    _, code = preview(path, capsys)
    path.write_text(path.read_text().replace("Título curto", "Título curtíssimo"))

    assert approve(path, code) == 1
    assert world.writes() == []
    assert "changed" in capsys.readouterr().err


def test_approve_expires_after_thirty_minutes(world, capsys, monkeypatch):
    path = create_draft()
    _, code = preview(path, capsys)
    monkeypatch.setattr(card, "_now", lambda: NOW + timedelta(minutes=31))

    assert approve(path, code) == 1
    assert world.writes() == []
    assert "expired" in capsys.readouterr().err

    monkeypatch.setattr(card, "_now", lambda: NOW + timedelta(minutes=29))
    _, code = preview(path, capsys)
    monkeypatch.setattr(card, "_now", lambda: NOW + timedelta(minutes=58))
    assert approve(path, code) == 0


def test_the_right_code_sends_exactly_the_previewed_requests_once(world, capsys):
    path = create_draft()
    _, code = preview(path, capsys)
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
    _, code = preview(path, capsys)
    assert approve(path, code) == 0
    count = len(world.writes())
    path = create_draft()

    assert approve(path, code) == 1
    assert len(world.writes()) == count


def test_a_204_answer_is_success(world, capsys):
    path = make_draft("e.md", "edit", key="TS-101", priority="High")
    _, code = preview(path, capsys)

    assert approve(path, code) == 0
    assert world.writes()[0]["method"] == "PUT"


def test_approve_reruns_the_checks_and_refuses_a_card_reassigned_since_the_preview(world, capsys):
    path = make_draft("c.md", "comment", "Oi.\n", key="TS-101")
    _, code = preview(path, capsys)
    world.set_card("TS-101", assignee="acc-other")

    assert approve(path, code) == 1
    assert world.writes() == []
    captured = capsys.readouterr()
    assert "not assigned to you" in captured.out + captured.err


def test_approve_refuses_when_the_requests_now_differ(world, capsys):
    path = create_draft()
    _, code = preview(path, capsys)
    world.set_sprints([{"id": 56, "name": "Sprint 56", "endDate": "2026-11-20T15:00:00.000Z"}])

    assert approve(path, code) == 1
    assert world.writes() == []
    assert "differ" in capsys.readouterr().err
    assert len(pending_files()) == 1


def test_approve_refuses_a_transition_that_disappeared(world, capsys):
    path = make_draft("m.md", "move", key="TS-101", to="Em Validação")
    _, code = preview(path, capsys)
    world.set_transitions("TS-101", [])

    assert approve(path, code) == 1
    assert world.writes() == []


def test_the_pending_record_is_deleted_before_anything_is_sent(world, capsys):
    path = create_draft()
    _, code = preview(path, capsys)
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
    _, code = preview(path, capsys)
    capsys.readouterr()

    assert approve(path, code) == 3

    out = capsys.readouterr().out
    assert "resultado incerto: confira no Jira" in out
    assert 'summary ~ "\\"[FRONT] Título \\\\\\"com aspas\\\\\\"\\""' in out
    assert len(world.writes()) == 1
    assert pending_files() == []
    assert not path.exists()
    kept = data_dir() / "cards" / "uncertain" / "create.md"
    assert kept.exists()
    assert str(kept) in out


def test_a_connection_error_after_sending_is_uncertain(world, capsys, monkeypatch):
    path = make_draft("c.md", "comment", "Oi.\n", key="TS-101")
    _, code = preview(path, capsys)
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
    _, code = preview(path, capsys)
    capsys.readouterr()

    assert approve(path, code) == 3

    captured = capsys.readouterr()
    assert "duedate: invalid" in captured.out + captured.err
    assert "resultado incerto" not in captured.out
    assert not path.exists()
    assert (data_dir() / "cards" / "uncertain" / "e.md").exists()
    assert str(data_dir() / "cards" / "uncertain" / "e.md") in captured.out


def folder_with_three():
    drafts = data_dir() / "cards" / "drafts"
    make_draft("1-comment.md", "comment", "Primeiro.\n", key="TS-101")
    make_draft("2-edit.md", "edit", key="TS-101", priority="High")
    make_draft("3-worklog.md", "worklog", key="TS-101", time="1h")
    return drafts


def test_a_folder_is_one_preview_and_one_approval_in_name_order(world, capsys):
    drafts = folder_with_three()
    _, code = preview(drafts, capsys)
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
    _, code = preview(drafts, capsys)
    capsys.readouterr()

    assert approve(drafts, code) == 3

    out = capsys.readouterr()
    text = out.out + out.err
    assert [r["path"].rsplit("/", 1)[1] for r in world.writes()] == ["comment", "TS-101"]
    assert "1-comment.md" in text.split("2-edit.md")[0]
    assert "nope" in text
    assert "3-worklog.md" in text
    assert sorted(p.name for p in drafts.iterdir()) == ["3-worklog.md"]
    assert [p.name for p in (data_dir() / "cards" / "uncertain").iterdir()] == ["2-edit.md"]
    assert [p.name for p in (data_dir() / "cards" / "done").iterdir()] == ["1-comment.md"]


def test_a_batch_with_one_bad_draft_previews_nothing(world, capsys):
    drafts = folder_with_three()
    make_draft("4-bad.md", "comment", "Oi.\n", key="TS-102")

    assert main(["card", "preview", str(drafts)]) == 1

    assert "4-bad.md" in capsys.readouterr().out
    assert pending_files() == []


def test_a_draft_added_to_the_folder_after_the_preview_is_refused(world, capsys):
    drafts = folder_with_three()
    _, code = preview(drafts, capsys)
    make_draft("4-more.md", "comment", "Extra.\n", key="TS-101")

    assert approve(drafts, code) == 1
    assert world.writes() == []


def test_the_pending_record_of_a_failed_approval_is_not_reusable(world, capsys):
    path = make_draft("c.md", "comment", "Oi.\n", key="TS-101")
    world.fake.routes[("POST", "/rest/api/3/issue/TS-101/comment")] = (500, "{}")
    _, code = preview(path, capsys)
    assert approve(path, code) == 3
    count = len(world.writes())

    assert approve(path, code) == 1
    assert len(world.writes()) == count


def test_apply_of_an_empty_folder_is_a_problem(world, capsys):
    folder = data_dir() / "cards" / "drafts"
    folder.mkdir(parents=True)

    assert main(["card", "preview", str(folder)]) == 1


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


@pytest.mark.parametrize("command", [["check"], ["epics"], ["preview"]])
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
    for name in ["board_id", "issue_type", "sprint_field"]:
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
    preview(create_draft(), capsys)

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
    _, code = preview(path, capsys)
    path.write_text(path.read_text() + "\n  \n")

    assert approve(path, code) == 1

    assert "changed" in capsys.readouterr().err
    assert world.writes() == []
    assert len(pending_files()) == 1


def test_a_renamed_draft_or_a_copy_elsewhere_is_refused_even_with_the_same_requests(world, capsys):
    drafts = data_dir() / "cards" / "drafts"
    make_draft("a.md", "move", key="TS-101", to="Em Validação")
    _, code = preview(drafts, capsys)
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


def test_the_code_changes_with_the_path_the_site_the_before_state_and_the_summary():
    request = {"method": "PUT", "path": "/rest/api/3/issue/TS-1", "body": {"fields": {"a": 1}}}
    site, lines = "https://example.atlassian.net", ["[1/1] Editar card TS-1 (e.md)"]
    base = card.approval_code(site, [request], [{}], lines)

    assert base == card.approval_code(site + "/", [request], [{}], lines)
    other_key = {**request, "path": "/rest/api/3/issue/TS-2"}
    assert card.approval_code(site, [other_key], [{}], lines) != base
    assert card.approval_code("https://other.atlassian.net", [request], [{}], lines) != base
    other_method = {**request, "method": "POST"}
    assert card.approval_code(site, [other_method], [{}], lines) != base
    other_body = {**request, "body": {"fields": {"a": 2}}}
    assert card.approval_code(site, [other_body], [{}], lines) != base
    assert card.approval_code(site, [request], [{"a": 1}], lines) != base
    assert card.approval_code(site, [request], [{}], [*lines, "  Prazo: 2026-11-05"]) != base
    assert card.approval_code(site, [request], [{}], ["[1/1] Outro texto"]) != base


def test_a_pending_record_for_another_site_is_refused(world, capsys):
    path = make_draft("c.md", "comment", "Oi.\n", key="TS-101")
    _, code = preview(path, capsys)
    record_path, record = read_record()
    record["site"] = "https://other.atlassian.net"
    forged = card.approval_code(
        record["site"], record["requests"], record["before"], record["summary"]
    )
    record["code"] = forged
    record_path.with_name(f"{forged}.json").write_text(json.dumps(record))
    record_path.with_name(f"{forged}.json").chmod(0o600)

    assert approve(path, forged) == 1

    assert "differ" in capsys.readouterr().err
    assert world.writes() == []


def test_a_draft_outside_the_drafts_folder_is_refused_everywhere(world, capsys, tmp_path):
    outside = tmp_path / "elsewhere.md"
    outside.write_text(create_draft().read_text())

    assert main(["card", "check", str(outside)]) == 1
    assert "inside" in capsys.readouterr().out
    assert main(["card", "preview", str(outside)]) == 1
    assert main(["card", "preview", str(tmp_path)]) == 1
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
    assert main(["card", "preview", str(drafts)]) == 1
    assert "symlink" in capsys.readouterr().err
    assert main(["card", "preview", str(drafts / "link.md")]) == 1
    folder_link = data_dir() / "cards" / "linked"
    folder_link.symlink_to(tmp_path)
    assert main(["card", "preview", str(folder_link)]) == 1
    assert world.fake.requests == []
    assert outside.exists()


def test_a_symlink_inside_the_drafts_folder_is_also_refused(world, capsys):
    drafts = data_dir() / "cards" / "drafts"
    real = make_draft("real.md", "comment", "Oi.\n", key="TS-101")
    (drafts / "alias.md").symlink_to(real)

    assert main(["card", "preview", str(drafts)]) == 1
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
    _, code = preview(path, capsys)
    world.set_card("TS-101", fields={"summary": "[FRONT] Alguém mexeu"})

    assert approve(path, code) == 1

    assert "o card mudou no Jira desde a prévia; rode o ws card preview de novo" in (
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
    _, code = preview(path, capsys)
    world.set_card("TS-101", fields=change)

    assert approve(path, code) == 1
    assert world.writes() == []


def test_an_edit_of_the_description_is_refused_when_the_old_text_changed(world, capsys):
    path = make_draft(
        "e.md", "edit", "## Contexto\nNovo.\n\n## Pronto quando\n- ok\n", key="TS-101"
    )
    _, code = preview(path, capsys)
    world.set_card("TS-101", description=to_adf(SECTIONS + "\nmais uma linha\n"))

    assert approve(path, code) == 1
    assert world.writes() == []


def test_an_edit_whose_card_did_not_change_is_still_approved(world, capsys):
    path = make_draft("e.md", "edit", key="TS-101", title="[FRONT] Novo título")
    _, code = preview(path, capsys)
    world.set_card("TS-101", fields={"duedate": "2026-12-01"})

    assert approve(path, code) == 0


def test_a_move_is_refused_when_the_status_changed_since_the_preview(world, capsys):
    path = make_draft("m.md", "move", key="TS-101", to="Em Validação")
    _, code = preview(path, capsys)
    status = {"name": "Blocked", "statusCategory": {"key": "indeterminate"}}
    world.set_card("TS-101", status=status)

    assert approve(path, code) == 1

    assert "o card mudou no Jira desde a prévia" in capsys.readouterr().err
    assert world.writes() == []


def test_a_pending_record_dated_in_the_future_is_refused(world, capsys, monkeypatch):
    path = make_draft("c.md", "comment", "Oi.\n", key="TS-101")
    _, code = preview(path, capsys)
    monkeypatch.setattr(card, "_now", lambda: NOW - timedelta(minutes=5))

    assert approve(path, code) == 1

    assert "future" in capsys.readouterr().err
    assert world.writes() == []


def test_a_pending_record_that_is_not_private_is_refused(world, capsys):
    path = make_draft("c.md", "comment", "Oi.\n", key="TS-101")
    _, code = preview(path, capsys)
    record_path, _ = read_record()
    record_path.chmod(0o644)

    assert approve(path, code) == 1
    assert "not a private file" in capsys.readouterr().err
    assert world.writes() == []


def test_a_pending_record_owned_by_someone_else_is_refused(world, capsys, monkeypatch):
    path = make_draft("c.md", "comment", "Oi.\n", key="TS-101")
    _, code = preview(path, capsys)
    monkeypatch.setattr(card.os, "getuid", lambda: os.stat(data_dir()).st_uid + 1)

    assert approve(path, code) == 1
    assert "not a private file" in capsys.readouterr().err
    assert world.writes() == []


def test_a_pending_record_that_is_a_symlink_is_refused(world, capsys, tmp_path):
    path = make_draft("c.md", "comment", "Oi.\n", key="TS-101")
    _, code = preview(path, capsys)
    record_path, _ = read_record()
    target = tmp_path / "real.json"
    record_path.rename(target)
    record_path.symlink_to(target)

    assert approve(path, code) == 1
    assert world.writes() == []


def test_a_day_rollover_between_preview_and_approve_says_so(world, capsys, monkeypatch):
    world.set_card("TS-101", **{START_FIELD: None})
    path = make_draft("m.md", "move", key="TS-101", to="Em Andamento")
    monkeypatch.setattr(card, "_now", lambda: datetime(2026, 10, 28, 2, 50, tzinfo=UTC))
    _, code = preview(path, capsys)
    monkeypatch.setattr(card, "_now", lambda: datetime(2026, 10, 28, 3, 10, tzinfo=UTC))

    assert approve(path, code) == 1

    assert "a data de hoje mudou desde a prévia; rode o ws card preview de novo" in (
        capsys.readouterr().err
    )
    assert world.writes() == []


def test_a_day_rollover_does_not_matter_when_nothing_depends_on_today(world, capsys, monkeypatch):
    path = create_draft()
    monkeypatch.setattr(card, "_now", lambda: datetime(2026, 10, 28, 2, 50, tzinfo=UTC))
    _, code = preview(path, capsys)
    monkeypatch.setattr(card, "_now", lambda: datetime(2026, 10, 28, 3, 10, tzinfo=UTC))

    assert approve(path, code) == 0


def test_the_printed_approve_command_is_shell_quoted(world, capsys):
    drafts = data_dir() / "cards" / "drafts"
    path = make_draft("a b; echo $x.md", "comment", "Oi.\n", key="TS-101")

    out, code = preview(path, capsys)

    assert f"ws card apply '{path}' --approve {code}" in out
    assert drafts.exists()


def test_a_pending_record_that_cannot_be_saved_is_a_clear_message(world, capsys, monkeypatch):
    original = os.open

    def deny(path, *args, **kwargs):
        if str(path).endswith(".json"):
            raise PermissionError(13, "Permission denied")
        return original(path, *args, **kwargs)

    monkeypatch.setattr(card.os, "open", deny)

    assert main(["card", "preview", str(create_draft())]) == 1

    captured = capsys.readouterr()
    assert "could not save the pending record" in captured.err
    assert "Código de aprovação" not in captured.out
    assert pending_files() == []


def test_an_unexpected_error_after_a_write_still_reports_it_and_lists_the_rest(
    world, capsys, monkeypatch
):
    drafts = folder_with_three()
    _, code = preview(drafts, capsys)
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
    assert sorted(p.name for p in drafts.iterdir()) == ["3-worklog.md"]
    assert [p.name for p in (data_dir() / "cards" / "uncertain").iterdir()] == ["2-edit.md"]
    assert [p.name for p in (data_dir() / "cards" / "done").iterdir()] == ["1-comment.md"]


def test_a_failure_moving_an_applied_draft_does_not_hide_the_write(world, capsys, monkeypatch):
    drafts = folder_with_three()
    _, code = preview(drafts, capsys)
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
    _, code = preview(path, capsys)
    capsys.readouterr()

    assert approve(path, code) == 0

    assert "Criado: create.md" in capsys.readouterr().out
    assert not path.exists()


def test_approve_stops_a_forged_request_shape_and_keeps_the_record(world, capsys, monkeypatch):
    forged = cardrules.Verdict(
        requests=[{"method": "DELETE", "path": "/rest/api/3/issue/TS-101", "body": {}}],
        preview=["forjado"],
        resolved={"today": "2026-10-27"},
    )
    monkeypatch.setattr(cardrules, "check", lambda context, draft: forged)
    path = make_draft("c.md", "comment", "Oi.\n", key="TS-101")
    _, code = preview(path, capsys)

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
    _, code = preview(path, capsys)
    capsys.readouterr()
    before = len(world.fake.requests)

    write_claude_settings(claude_settings, ask=("Bash(other:*)",))
    assert approve(path, code) == 2
    assert "Bash(ws card apply:*)" in capsys.readouterr().err

    write_claude_settings(claude_settings, hook=False)
    assert approve(path, code) == 2
    assert "approval_gate.py" in capsys.readouterr().err

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

    preview(create_draft(), capsys)


def test_a_failed_draft_never_comes_back_in_a_later_preview_of_the_folder(world, capsys):
    drafts = folder_with_three()
    world.fake.routes[("PUT", "/rest/api/3/issue/TS-101")] = (500, "{}")
    _, code = preview(drafts, capsys)
    assert approve(drafts, code) == 3
    capsys.readouterr()
    world.fake.routes[("PUT", "/rest/api/3/issue/TS-101")] = (204, "")

    out, _ = preview(drafts, capsys)

    assert "3-worklog.md" in out
    assert "2-edit.md" not in out


def test_a_second_failed_draft_with_the_same_name_does_not_overwrite_the_first(world, capsys):
    world.fake.routes[("POST", "/rest/api/3/issue/TS-101/comment")] = (400, "{}")
    for text in ["Um.\n", "Dois.\n"]:
        path = make_draft("c.md", "comment", text, key="TS-101")
        _, code = preview(path, capsys)
        assert approve(path, code) == 3

    assert sorted(p.name for p in (data_dir() / "cards" / "uncertain").iterdir()) == [
        "c-1.md",
        "c.md",
    ]


def test_applying_a_draft_removes_the_other_pending_records_that_mention_it(world, capsys):
    drafts = folder_with_three()
    _, folder_code = preview(drafts, capsys)
    single = drafts / "1-comment.md"
    _, single_code = preview(single, capsys)
    other = drafts / "elsewhere" / "9-other.md"
    other.parent.mkdir()
    other.write_text(make_draft("tmp.md", "comment", "Outro.\n", key="TS-101").read_text())
    (drafts / "tmp.md").unlink()
    _, other_code = preview(other, capsys)
    assert len(pending_files()) == 3
    capsys.readouterr()

    assert approve(drafts, folder_code) == 0

    assert [p.name for p in pending_files()] == [f"{other_code}.json"]
    assert single_code not in [p.stem for p in pending_files()]
    assert approve(other, other_code) == 0


def test_the_priority_on_a_later_page_of_the_create_screen_is_found(world, capsys):
    base = "/rest/api/3/issue/createmeta/TS/issuetypes/3"
    del world.fake.routes[("GET", base)]
    page = {"total": 2, "fields": [{"fieldId": "summary"}]}
    world.fake.routes[("GET", base, "0")] = (200, json.dumps(page))
    later = {"total": 2, "fields": [{"fieldId": "priority", "allowedValues": [{"name": "High"}]}]}
    world.fake.routes[("GET", base, "1")] = (200, json.dumps(later))

    passing(create_draft(), capsys)


def test_a_transition_without_an_id_is_refused(world, capsys):
    world.set_transitions(
        "TS-101", [{"name": "Validar", "to": {"name": "Em Validação"}, "fields": {}}]
    )

    message = problems(make_draft("m.md", "move", key="TS-101", to="Em Validação"), capsys)

    assert "no id" in message


def test_a_symlinked_or_foreign_credentials_file_has_its_own_message(
    world, capsys, ws_config, tmp_path
):
    real = tmp_path / "elsewhere"
    real.write_text('[jira]\ntoken = "stolen"\n', encoding="utf-8")
    (ws_config / "credentials").unlink()
    (ws_config / "credentials").symlink_to(real)

    assert main(["card", "check", str(OPS["comment"]("TS-101"))]) == 2

    err = capsys.readouterr().err
    assert "symlink" in err and "no Jira API key" not in err
    assert world.fake.requests == []


def test_a_failed_draft_also_drops_the_pending_records_that_mention_it(world, capsys):
    drafts = folder_with_three()
    world.fake.routes[("PUT", "/rest/api/3/issue/TS-101")] = (400, "{}")
    _, folder_code = preview(drafts, capsys)
    edit = drafts / "2-edit.md"
    _, edit_code = preview(edit, capsys)
    worklog = drafts / "3-worklog.md"
    _, worklog_code = preview(worklog, capsys)
    assert len(pending_files()) == 3
    capsys.readouterr()

    assert approve(drafts, folder_code) == 3

    assert [p.stem for p in pending_files()] == [worklog_code]
    assert edit_code not in [p.stem for p in pending_files()]


def test_an_uncertain_draft_also_drops_the_pending_records_that_mention_it(world, capsys):
    drafts = data_dir() / "cards" / "drafts"
    make_draft("1-c.md", "comment", "Um.\n", key="TS-101")
    make_draft("2-c.md", "comment", "Dois.\n", key="TS-101")
    world.fake.routes[("POST", "/rest/api/3/issue/TS-101/comment")] = (502, "{}")
    _, folder_code = preview(drafts, capsys)
    preview(drafts / "1-c.md", capsys)
    assert len(pending_files()) == 2

    assert approve(drafts, folder_code) == 3

    assert pending_files() == []


def test_the_session_id_is_the_shells_session():
    assert REAL_SESSION_ID() == os.getsid(0)


def test_the_preview_stores_its_session_id(world, capsys, monkeypatch):
    monkeypatch.setattr(card, "_session_id", lambda: 4242)
    path = make_draft("c.md", "comment", "Oi.\n", key="TS-101")

    preview(path, capsys)

    assert read_record()[1]["sid"] == 4242


def test_preview_and_approve_in_the_same_session_are_refused(world, capsys, monkeypatch):
    monkeypatch.setattr(card, "_session_id", lambda: 4242)
    path = make_draft("c.md", "comment", "Oi.\n", key="TS-101")
    _, code = preview(path, capsys)
    capsys.readouterr()
    before = len(world.fake.requests)

    assert approve(path, code) == 1

    assert "a prévia e a aprovação precisam ser passos separados" in capsys.readouterr().err
    assert len(world.fake.requests) == before
    assert world.writes() == []
    assert len(pending_files()) == 1

    monkeypatch.setattr(card, "_session_id", lambda: 4243)
    assert approve(path, code) == 0


def test_the_real_session_id_stops_two_calls_in_one_process(world, capsys, monkeypatch):
    monkeypatch.setattr(card, "_session_id", REAL_SESSION_ID)
    path = make_draft("c.md", "comment", "Oi.\n", key="TS-101")
    _, code = preview(path, capsys)
    capsys.readouterr()

    assert approve(path, code) == 1

    assert "passos separados" in capsys.readouterr().err
    assert world.writes() == []


def test_a_record_without_a_session_id_is_refused(world, capsys):
    path = make_draft("c.md", "comment", "Oi.\n", key="TS-101")
    _, code = preview(path, capsys)
    record_path, record = read_record()
    del record["sid"]
    record_path.write_text(json.dumps(record))

    assert approve(path, code) == 1
    assert world.writes() == []


def two_drafts():
    return [
        make_draft("a.md", "comment", "Oi.\n", key="TS-101"),
        make_draft("b.md", "move", key="TS-101", to="Em Validação"),
    ]


def test_the_pending_record_keeps_the_summary_the_preview_prints(world, capsys):
    path = make_draft("m.md", "move", key="TS-101", to="Em Validação")

    out, _ = preview(path, capsys)

    _, record = read_record()
    assert record["summary"][0] == "[1/1] Mover card TS-101 (m.md)"
    assert "  Mover o card TS-101" in record["summary"]
    assert "  Status: In Progress -> Em Validação" in record["summary"]
    assert all(line in out for line in record["summary"])
    assert not any("/rest/api" in line for line in record["summary"])


def test_the_summary_has_one_header_per_draft_and_the_warnings(world, capsys):
    world.set_card("TS-101", duedate="2026-10-20", **{START_FIELD: None})
    folder = data_dir() / "cards" / "drafts"
    make_draft("a.md", "comment", "Oi.\n", key="TS-101")
    make_draft("b.md", "move", key="TS-101", to="Em Andamento")

    out, _ = preview(folder, capsys)

    _, record = read_record()
    headers = [line for line in record["summary"] if line.startswith("[")]
    assert headers == [
        "[1/2] Comentar no card TS-101 (a.md)",
        "[2/2] Mover card TS-101 (b.md)",
    ]
    assert any(line.startswith("  Aviso: ") for line in record["summary"])
    assert "Criar card" not in out


def test_a_create_header_has_no_card_key(world, capsys):
    preview(create_draft(), capsys)

    _, record = read_record()
    assert record["summary"][0] == "[1/1] Criar card (create.md)"


def test_a_record_with_an_edited_summary_and_the_same_code_is_refused(world, capsys):
    path = make_draft("c.md", "comment", "Oi.\n", key="TS-101")
    _, code = preview(path, capsys)
    record_path, record = read_record()
    record["summary"] = ["[1/1] Comentar no card TS-101 (c.md)", "  Um texto mais simpático"]
    record_path.write_text(json.dumps(record))
    record_path.chmod(0o600)

    assert approve(path, code) == 1

    assert "foi alterado" in capsys.readouterr().err
    assert world.writes() == []
    assert record_path.exists()


@pytest.mark.parametrize(
    "key,value",
    [
        ("requests", [{"method": "POST", "path": "/rest/api/3/issue/TS-101/comment", "body": {}}]),
        ("before", [{"status": "Done"}]),
        ("site", "https://other.atlassian.net"),
        ("summary", None),
    ],
)
def test_a_record_that_does_not_hash_to_its_code_is_refused(world, capsys, key, value):
    path = make_draft("c.md", "comment", "Oi.\n", key="TS-101")
    _, code = preview(path, capsys)
    record_path, record = read_record()
    record[key] = value
    record_path.write_text(json.dumps(record))
    record_path.chmod(0o600)

    assert approve(path, code) == 1

    assert "foi alterado" in capsys.readouterr().err
    assert world.writes() == []


def test_a_record_without_a_summary_is_refused(world, capsys):
    path = make_draft("c.md", "comment", "Oi.\n", key="TS-101")
    _, code = preview(path, capsys)
    record_path, record = read_record()
    del record["summary"]
    record_path.write_text(json.dumps(record))
    record_path.chmod(0o600)

    assert approve(path, code) == 1

    assert "foi alterado" in capsys.readouterr().err
    assert world.writes() == []


def test_the_summary_changes_the_code(world, capsys):
    _, first = preview(make_draft("c.md", "comment", "Oi.\n", key="TS-101"), capsys)
    _, other_name = preview(make_draft("d.md", "comment", "Oi.\n", key="TS-101"), capsys)

    assert first != other_name


def at_a_terminal(monkeypatch, *answers, tty=True):
    """Both streams are TTYs, Claude Code is not around, and `input` answers from the list (an
    exception in the list is raised). Returns the prompts shown."""
    monkeypatch.setattr(card, "_interactive", REAL_INTERACTIVE)
    monkeypatch.setattr(humans, "under_agent_harness", lambda: False)
    monkeypatch.setattr(sys.stdin, "isatty", lambda: tty, raising=False)
    monkeypatch.setattr(sys.stdout, "isatty", lambda: tty, raising=False)
    monkeypatch.delenv("CLAUDECODE", raising=False)
    replies, prompts = iter(answers), []

    def fake_input(prompt=""):
        prompts.append(prompt)
        reply = next(replies)
        if isinstance(reply, BaseException):
            raise reply
        return reply

    monkeypatch.setattr("builtins.input", fake_input)
    return prompts


def prepared_comment(world, capsys):
    path = make_draft("c.md", "comment", "Oi.\n", key="TS-101")
    _, code = preview(path, capsys)
    capsys.readouterr()
    return path, code


@pytest.mark.parametrize("answer", ["s", "sim", "S", "SIM", " Sim ", "sIm\t"])
def test_by_hand_a_yes_sends_and_shows_the_summary_first(world, capsys, monkeypatch, answer):
    path, code = prepared_comment(world, capsys)
    prompts = at_a_terminal(monkeypatch, answer)

    assert approve(path, code) == 0

    out = capsys.readouterr().out
    assert prompts == ["Gravar no Jira? [s/N] "]
    assert "[1/1] Comentar no card TS-101 (c.md)" in out
    assert len(world.writes()) == 1
    assert pending_files() == []


@pytest.mark.parametrize("answer", ["n", "N", "", "nao", "não", "y", "yes", "ss", "s s", "sim!"])
def test_by_hand_anything_but_yes_sends_nothing_and_keeps_the_record(
    world, capsys, monkeypatch, answer
):
    path, code = prepared_comment(world, capsys)
    at_a_terminal(monkeypatch, answer)

    assert approve(path, code) == 1

    assert "Nada foi enviado." in capsys.readouterr().out
    assert world.writes() == []
    assert len(pending_files()) == 1


@pytest.mark.parametrize("error", [EOFError(), KeyboardInterrupt()])
def test_by_hand_end_of_input_sends_nothing(world, capsys, monkeypatch, error):
    path, code = prepared_comment(world, capsys)
    at_a_terminal(monkeypatch, error)

    assert approve(path, code) == 1

    assert "Nada foi enviado." in capsys.readouterr().out
    assert world.writes() == []
    assert len(pending_files()) == 1


def test_by_hand_needs_no_claude_settings_and_allows_the_same_session(
    world, capsys, monkeypatch, claude_settings
):
    path, code = prepared_comment(world, capsys)
    claude_settings.unlink()
    monkeypatch.setattr(card, "_session_id", lambda: 4242)
    _, record = read_record()
    record["sid"] = 4242
    record_path, _ = read_record()
    record_path.write_text(json.dumps(record))
    record_path.chmod(0o600)
    at_a_terminal(monkeypatch, "s")

    assert approve(path, code) == 0
    assert len(world.writes()) == 1


def test_by_hand_the_other_checks_still_come_first(world, capsys, monkeypatch):
    path, code = prepared_comment(world, capsys)
    prompts = at_a_terminal(monkeypatch, "s")

    path.write_text(path.read_text() + "mais um texto\n")
    assert approve(path, code) == 1
    assert "changed" in capsys.readouterr().err

    world.set_card("TS-101", assignee="acc-other")
    path.write_text(path.read_text().replace("mais um texto\n", ""))
    assert approve(path, code) == 1

    assert prompts == []
    assert world.writes() == []


def test_by_hand_the_live_recheck_still_refuses_before_the_question(world, capsys, monkeypatch):
    path = make_draft("m.md", "move", key="TS-101", to="Em Validação")
    _, code = preview(path, capsys)
    capsys.readouterr()
    world.set_card("TS-101", status={"name": "Em Validação", "statusCategory": {"key": "new"}})
    prompts = at_a_terminal(monkeypatch, "s")

    assert approve(path, code) == 1

    assert prompts == []
    assert world.writes() == []


def test_by_hand_a_tampered_record_is_refused_before_the_question(world, capsys, monkeypatch):
    path, code = prepared_comment(world, capsys)
    record_path, record = read_record()
    record["summary"] = ["Nada de mais"]
    record_path.write_text(json.dumps(record))
    record_path.chmod(0o600)
    prompts = at_a_terminal(monkeypatch, "s")

    assert approve(path, code) == 1

    assert prompts == []
    assert "foi alterado" in capsys.readouterr().err
    assert world.writes() == []


def test_without_a_terminal_both_rules_hold(world, capsys, monkeypatch, claude_settings):
    path, code = prepared_comment(world, capsys)
    prompts = at_a_terminal(monkeypatch, "s", tty=False)

    claude_settings.unlink()
    assert approve(path, code) == 2
    assert "not found" in capsys.readouterr().err

    write_claude_settings(claude_settings)
    monkeypatch.setattr(card, "_session_id", lambda: 4242)
    record_path, record = read_record()
    record["sid"] = 4242
    record_path.write_text(json.dumps(record))
    record_path.chmod(0o600)
    assert approve(path, code) == 1
    assert "passos separados" in capsys.readouterr().err

    assert prompts == []
    assert world.writes() == []


@pytest.mark.parametrize("stream", ["stdin", "stdout"])
def test_one_stream_that_is_not_a_terminal_is_not_interactive(monkeypatch, stream):
    at_a_terminal(monkeypatch, "s")
    assert card._interactive() is True

    monkeypatch.setattr(getattr(sys, stream), "isatty", lambda: False, raising=False)

    assert card._interactive() is False


@pytest.mark.parametrize("value", ["1", "0", ""])
def test_claude_code_in_the_environment_is_not_interactive(monkeypatch, value):
    at_a_terminal(monkeypatch, "s")

    monkeypatch.setenv("CLAUDECODE", value)

    assert card._interactive() is False


def fake_proc(tmp_path, monkeypatch, chain):
    """A /proc where this process descends from `chain` (nearest first) as (comm, cmdline words)."""
    root = tmp_path / "proc"
    pids = [os.getpid(), *range(5000, 5000 + len(chain))]
    processes = [("pytest", ["python3", "-m", "pytest"]), *chain]
    for index, (comm, words) in enumerate(processes):
        folder = root / str(pids[index])
        folder.mkdir(parents=True)
        parent = pids[index + 1] if index + 1 < len(pids) else 1
        (folder / "stat").write_text(f"{pids[index]} ({comm}) S {parent} 1 1 0\n")
        (folder / "comm").write_text(comm + "\n")
        (folder / "cmdline").write_bytes("\0".join(words).encode() + b"\0")
    monkeypatch.setattr(humans, "PROC", root)
    return root


@pytest.mark.parametrize(
    "harness",
    [
        ("claude", ["claude"]),
        ("node", ["node", "/usr/lib/node_modules/@anthropic-ai/claude-code/cli.js"]),
        ("node", ["/usr/bin/node", "/usr/lib/node_modules/@openai/codex/bin/codex.js"]),
        ("MainThread", ["~/.local/bin/opencode", "--flag"]),
        ("python3", ["python3", "-m", "aider"]),
        ("cursor-agent", ["x"]),
        ("goose", ["goose"]),
        ("gemini", ["gemini"]),
    ],
)
def test_an_agent_harness_ancestor_is_not_by_hand(tmp_path, monkeypatch, harness):
    monkeypatch.setattr(humans, "under_agent_harness", REAL_UNDER_HARNESS)
    shell = ("bash", ["bash", "-c", "ws card apply"])
    fake_proc(tmp_path, monkeypatch, [("script", ["script", "-qec", "ws"]), shell, harness])

    assert humans.under_agent_harness() is True


def test_a_terminal_without_a_harness_ancestor_is_by_hand(tmp_path, monkeypatch):
    monkeypatch.setattr(humans, "under_agent_harness", REAL_UNDER_HARNESS)
    chain = [("bash", ["-bash"]), ("tmux: server", ["tmux", "new", "claude-notes.md"])]
    fake_proc(tmp_path, monkeypatch, chain)

    assert humans.under_agent_harness() is False


def test_a_proc_that_cannot_be_read_is_not_by_hand(tmp_path, monkeypatch):
    monkeypatch.setattr(humans, "under_agent_harness", REAL_UNDER_HARNESS)
    monkeypatch.setattr(humans, "PROC", tmp_path / "missing")

    assert humans.under_agent_harness() is True


def test_a_pseudo_terminal_run_by_the_harness_is_not_interactive(tmp_path, monkeypatch):
    at_a_terminal(monkeypatch, "s")
    monkeypatch.setattr(humans, "under_agent_harness", REAL_UNDER_HARNESS)
    fake_proc(tmp_path, monkeypatch, [("script", ["script"]), ("claude", ["claude"])])

    assert card._interactive() is False


def test_the_by_hand_limit_says_what_the_gate_really_asks_for():
    doc = " ".join(humans.by_hand.__doc__.split())

    assert "only when the program they start is one it watches" in doc
    for program in ("ws", "git", "gh", "curl", "wget"):
        assert f"`{program}`" in doc
    assert "double fork" in doc
    assert "escapes the walk" in doc


def test_drafts_folder_is_private_inside_the_drafts_root():
    folder = card.drafts_folder("sync-20261105-120000")
    assert folder == data_dir() / "cards" / "drafts" / "sync-20261105-120000"
    assert stat.S_IMODE(folder.stat().st_mode) == 0o700
    assert folder.resolve().is_relative_to(card._drafts_root())


def test_drafts_folder_refuses_an_existing_name():
    card.drafts_folder("sync-1")
    with pytest.raises(FileExistsError):
        card.drafts_folder("sync-1")


@pytest.mark.parametrize("name", ["", ".", "..", "../x", "a/b"])
def test_drafts_folder_refuses_a_name_that_leaves_the_root(name):
    with pytest.raises(ValueError):
        card.drafts_folder(name)
