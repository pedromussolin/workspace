import copy
import json
from datetime import date

import pytest

from ws import approval, card, contracts
from ws.carddraft import Draft
from ws.tracker import write
from ws.tracker.port import TrackerError

DRAFTS = {
    "create": Draft(
        "create",
        {"type": "task", "priority": "Medium", "epic": "TS-100", "due": date(2026, 11, 20)},
        "Tarefa de exemplo",
        "## Contexto\n\nTexto.\n",
        "a" * 64,
    ),
    "edit": Draft(
        "edit",
        {"key": "TS-101", "title": "Novo título", "start": date(2026, 11, 16)},
        None,
        "",
        "b" * 64,
    ),
    "move": Draft("move", {"key": "TS-101", "to": "Em andamento"}, None, "", "c" * 64),
    "comment": Draft("comment", {"key": "TS-101"}, None, "Um comentário.\n", "d" * 64),
    "worklog": Draft(
        "worklog",
        {"key": "TS-101", "time": "1h 30m", "day": date(2026, 11, 15)},
        None,
        "",
        "e" * 64,
    ),
    "link": Draft("link", {"key": "TS-101", "blocks": ["TS-102", "TS-103"]}, None, "", "f" * 64),
}


def plan_fixture() -> dict:
    return {
        "$schema": "card-plan",
        "version": 1,
        "tracker": "jira",
        "target": "https://example.atlassian.net/",
        "today": "2026-11-15",
        "steps": [
            {
                "draft": {"path": "/d/a.md", "sha256": "1" * 64},
                "op": "create",
                "card": None,
                "title": "Tarefa",
                "preview": ["Criar"],
                "warnings": [],
                "problems": [],
                "before": {},
                "native": [
                    {"method": "POST", "path": "/rest/api/3/issue", "body": {"a": 1}, "x": 9},
                    {"method": "PUT", "path": "/rest/api/3/issue/TS-1", "body": {"b": 2}},
                ],
            },
            {
                "draft": {"path": "/d/b.md", "sha256": "2" * 64},
                "op": "move",
                "card": "TS-2",
                "title": None,
                "preview": ["Mover"],
                "warnings": [],
                "problems": [],
                "before": {"status": "A fazer"},
                "native": [{"method": "POST", "path": "/t", "body": {"c": 3}}],
            },
        ],
        "summary": ["[1/2] Criar", "[2/2] Mover"],
        "code": "0123456789ab",
    }


@pytest.mark.parametrize("op", write.OPS)
def test_draft_to_document_for_each_op(op):
    draft = DRAFTS[op]
    document = write.to_document(draft)
    assert document["$schema"] == "card-write"
    assert document["version"] == 1
    assert document["op"] == op
    for name, value in draft.values.items():
        expected = value.isoformat() if isinstance(value, date) else value
        assert document[name] == expected
    assert ("title" in document) == (draft.title is not None or "title" in draft.values)
    assert ("body" in document) == bool(draft.body.strip())
    json.dumps(document)


def test_document_round_trips_to_the_same_draft_values():
    for draft in DRAFTS.values():
        document = write.to_document(draft)
        back = write.from_document(document)
        assert back.op == draft.op
        assert back.values == draft.values
        assert back.title == draft.title
        assert back.body == (draft.body if draft.body.strip() else "")
        assert back.sha256 == write.from_document(copy.deepcopy(document)).sha256


def test_documents_of_each_op_validate():
    for draft in DRAFTS.values():
        assert write.check_document(write.to_document(draft)) == []


def test_schema_refuses_unknown_key_bad_enum_and_version():
    document = write.to_document(DRAFTS["move"])
    assert contracts.validate({**document, "extra": 1}, "card-write")
    assert contracts.validate({**document, "op": "delete"}, "card-write")
    assert write.check_document({**document, "version": 2})
    assert write.check_document({**document, "$schema": "nope"})
    assert write.check_document({**document, "type": "story"})
    assert write.check_document({**document, "extra": 1})
    assert write.check_document({k: v for k, v in document.items() if k != "key"})
    assert write.check_document({**document, "blocks": ["TS-1"]})
    assert write.check_document({**write.to_document(DRAFTS["link"]), "blocks": "TS-1"})


def test_plan_and_result_schemas_validate():
    assert contracts.validate(plan_fixture(), "card-plan") == []
    bad = plan_fixture()
    bad["steps"][0]["extra"] = 1
    assert contracts.validate(bad, "card-plan")
    result = {
        "$schema": "card-result",
        "version": 1,
        "steps": [
            {
                "draft": {"path": "/d/a.md", "sha256": "1" * 64},
                "status": "applied",
                "sent": [{"method": "POST", "path": "/p", "body": {}}],
                "created": None,
                "url": None,
                "error": None,
            }
        ],
    }
    assert contracts.validate(result, "card-result") == []
    result["steps"][0]["status"] = "done"
    assert contracts.validate(result, "card-result")


def test_digest_material_has_the_frozen_keys():
    material = write.digest_material(plan_fixture())
    assert list(material) == ["site", "requests", "before", "summary"]
    assert material["site"] == "https://example.atlassian.net"
    assert material["requests"] == [
        {"method": "POST", "path": "/rest/api/3/issue", "body": {"a": 1}},
        {"method": "PUT", "path": "/rest/api/3/issue/TS-1", "body": {"b": 2}},
        {"method": "POST", "path": "/t", "body": {"c": 3}},
    ]
    assert material["before"] == [{}, {"status": "A fazer"}]
    assert material["summary"] == ["[1/2] Criar", "[2/2] Mover"]


def test_plan_code_equals_card_approval_code():
    plan = plan_fixture()
    material = write.digest_material(plan)
    assert write.plan_code(plan) == approval.digest(material)
    assert write.plan_code(plan) == card.approval_code(
        plan["target"], material["requests"], material["before"], plan["summary"]
    )


def test_pending_record_has_the_nine_keys():
    plan = plan_fixture()
    record = write.pending_record(plan, created_at="2026-11-15T10:00:00-03:00", sid=42)
    assert list(record) == [
        "code",
        "created_at",
        "site",
        "today",
        "sid",
        "drafts",
        "requests",
        "before",
        "summary",
    ]
    assert record["code"] == write.plan_code(plan)
    assert record["site"] == "https://example.atlassian.net"
    assert record["sid"] == 42
    assert record["drafts"] == [step["draft"] for step in plan["steps"]]
    assert record["requests"] == write.digest_material(plan)["requests"]


def test_record_code_is_the_code_of_the_pending_record():
    record = write.pending_record(plan_fixture(), created_at="2026-11-15T10:00:00-03:00", sid=42)

    assert write.record_code(record) == record["code"]
    assert write.record_code({**record, "summary": ["[1/2] Outro texto"]}) != record["code"]
    assert write.record_code({**record, "site": "https://other.atlassian.net"}) != record["code"]


class Writer:
    def created_key(self, reply):
        return reply["key"]

    def card_url(self, key):
        return f"https://example.atlassian.net/browse/{key}"


def run(send):
    return list(write.apply_steps(Writer(), plan_fixture(), send))


def test_apply_steps_sends_each_native_call_once():
    sent = []

    def send(call):
        sent.append(call)
        return {"key": "TS-9"}

    steps = run(send)
    assert [call["path"] for call in sent] == ["/rest/api/3/issue", "/rest/api/3/issue/TS-1", "/t"]
    assert [step["status"] for step in steps] == ["applied", "applied"]
    assert steps[0]["created"] == "TS-9"
    assert steps[1]["created"] is None
    assert len(steps[0]["sent"]) == 2
    assert steps[0]["draft"] == plan_fixture()["steps"][0]["draft"]


def test_apply_steps_stops_at_the_first_failure():
    def send(call):
        if call["path"] == "/rest/api/3/issue/TS-1":
            raise TrackerError("boom")
        return {"key": "TS-9"}

    steps = run(send)
    assert len(steps) == 1
    assert steps[0]["status"] == "failed"
    assert steps[0]["error"] == "boom"
    assert len(steps[0]["sent"]) == 1


def test_apply_steps_marks_uncertain_tracker_errors():
    error = TrackerError("timeout")
    error.uncertain = True

    def send(call):
        raise error

    [step] = run(send)
    assert step["status"] == "uncertain"


def test_apply_steps_marks_other_errors_uncertain():
    def send(call):
        raise KeyError("x")

    [step] = run(send)
    assert step["status"] == "uncertain"
    assert step["error"] == "KeyError: 'x'"


def test_apply_steps_marks_a_reply_without_key_uncertain():
    [step] = run(lambda call: {})
    assert step["status"] == "uncertain"
    assert step["error"] == "KeyError: 'key'"
    assert len(step["sent"]) == 2


def test_apply_steps_marks_a_create_without_calls_uncertain():
    plan = plan_fixture()
    plan["steps"][0]["native"] = []
    [step] = list(write.apply_steps(Writer(), plan, lambda call: {"key": "TS-9"}))
    assert step["status"] == "uncertain"
    assert step["sent"] == []


class GuardedWriter(Writer):
    def guard(self, calls):
        return next((call["path"] for call in calls if "OTHER" in call["path"]), None)


def after_create_plan():
    plan = plan_fixture()
    plan["steps"] = plan["steps"][:1]
    plan["steps"][0]["native"] = [
        {"method": "POST", "path": "/rest/api/3/issue", "body": {}},
        {"method": "PUT", "path": f"/rest/api/3/issue/{write.CREATED}", "body": {"fields": {}}},
    ]
    return plan


def test_apply_steps_puts_the_new_key_in_a_later_request_of_a_create():
    sent = []

    def send(call):
        sent.append(call)
        return {"key": "TS-9"}

    [step] = list(write.apply_steps(GuardedWriter(), after_create_plan(), send))

    assert [call["path"] for call in sent] == ["/rest/api/3/issue", "/rest/api/3/issue/TS-9"]
    assert step["status"] == "applied"
    assert [call["path"] for call in step["sent"]] == [call["path"] for call in sent]
    assert write.CREATED in after_create_plan()["steps"][0]["native"][1]["path"]


def test_apply_steps_refuses_a_new_key_the_guard_refuses_and_keeps_it_in_the_result():
    sent = []

    def send(call):
        sent.append(call)
        return {"key": "OTHER-9"}

    [step] = list(write.apply_steps(GuardedWriter(), after_create_plan(), send))

    assert len(sent) == 1
    assert step["status"] == "failed"
    assert step["created"] == "OTHER-9"
    assert "leads outside the allowed requests" in step["error"]


def test_apply_steps_keeps_the_key_of_a_card_whose_second_request_failed():
    def send(call):
        if call["method"] == "PUT":
            raise TrackerError("no field")
        return {"key": "TS-9"}

    [step] = list(write.apply_steps(GuardedWriter(), after_create_plan(), send))

    assert (step["status"], step["created"], len(step["sent"])) == ("failed", "TS-9", 1)


def test_apply_steps_calls_a_create_without_a_key_for_its_second_request_uncertain():
    [step] = list(write.apply_steps(GuardedWriter(), after_create_plan(), lambda call: {}))

    assert step["status"] == "uncertain"
    assert step["created"] is None
    assert len(step["sent"]) == 1


@pytest.mark.parametrize("value", ["2026-13-40", "2026-W46-7", "amanhã", "2026-1-5", 20261115])
def test_check_document_refuses_a_malformed_date(value):
    document = {**write.to_document(DRAFTS["edit"]), "due": value}
    assert write.check_document(document)
