import json
from importlib import resources

import pytest

from ws.contracts import check, load_schema, validate


def plan(**changes):
    document = {
        "version": 1,
        "task": "TS-5",
        "job": "demo-job",
        "switched_off": "2026-12-08",
        "days": 5,
        "timezone": "America/Sao_Paulo",
        "checks": [{"id": "a", "kind": "manual", "question": "ok?"}],
    }
    document.update(changes)
    return document


def result(**changes):
    document = {
        "version": 1,
        "day": "2026-12-09",
        "check": "a",
        "kind": "database",
        "value": 1,
        "expect": None,
        "verdict": "pass",
        "started": "2026-12-10T09:00:00Z",
        "finished": "2026-12-10T09:00:01Z",
        "window": ["2026-12-09T03:00:00Z", "2026-12-10T03:00:00Z"],
        "hash": "abc",
        "times": "run",
    }
    document.update(changes)
    return document


def test_validate_accepts_a_valid_plan():
    assert validate(plan(), "observe-plan") == []


def test_validate_missing_and_unexpected_keys():
    document = plan(foo=1)
    del document["task"]
    assert validate(document, "observe-plan") == [
        "$: missing required key task",
        "$.foo: unexpected key",
    ]


@pytest.mark.parametrize(
    ("schema", "document", "expected"),
    [
        ("observe-plan", plan(days="5"), ["$.days: expected integer, got string"]),
        ("observe-plan", plan(days=True), ["$.days: expected integer, got boolean"]),
        ("observe-result", result(value=1.5), []),
        ("observe-result", result(value=False), []),
        ("observe-result", result(expect=None), []),
        ("observe-result", result(expect="> 0"), []),
        ("observe-result", result(value="x"), ["$.value: expected number or boolean, got string"]),
        ("observe-result", result(by="tester"), []),
        ("observe-result", result(by=None), ["$.by: expected string, got null"]),
        ("observe-result", result(window={"from": "a"}), ["$.window: expected array, got object"]),
        ("observe-result", result(window=["a", 1]), ["$.window[1]: expected string, got integer"]),
    ],
)
def test_validate_types(schema, document, expected):
    assert validate(document, schema) == expected


def test_validate_enum_and_const():
    bad_kind = plan(checks=[{"id": "a", "kind": "nope"}])
    assert validate(bad_kind, "observe-plan") == [
        "$.checks[0].kind: expected one of observability, database, manual"
    ]
    assert validate(plan(version=2), "observe-plan") == ["$.version: expected 1"]


def test_validate_paths_inside_items():
    checks = [{"id": "a", "kind": "manual"}, {"kind": "manual"}]
    assert validate(plan(checks=checks), "observe-plan") == ["$.checks[1]: missing required key id"]


def test_load_schema_refuses_unknown_names_and_keywords():
    with pytest.raises(ValueError, match="unknown contract nope"):
        load_schema("nope")
    with pytest.raises(ValueError, match="unknown contract"):
        load_schema("../x")
    with pytest.raises(ValueError, match="pattern"):
        check({}, {"pattern": "x"})


def test_every_schema_pins_version_and_is_closed():
    folder = resources.files("ws") / "data" / "contracts"
    names = [
        p.name.removesuffix(".schema.json") for p in folder.iterdir() if p.name.endswith(".json")
    ]
    assert len(names) == 7
    for name in names:
        schema = load_schema(name)
        assert schema["properties"]["version"] == {"const": 1}
        assert "version" in schema["required"]
        assert schema["additionalProperties"] is False
        json.dumps(schema)


VALID = {
    "observe-plan": plan(),
    "observe-result": result(),
    "observe-status": {
        "version": 1,
        "today": "2026-12-10",
        "plans": [
            {
                "task": "TS-5",
                "project": "demo",
                "job": "demo-job",
                "days": 5,
                "due_day": "2026-12-15",
                "first_day": "2026-12-09",
                "day": 3,
                "pending": ["a"],
                "missing_days": ["2026-12-09"],
                "stale": [{"day": "2026-12-09", "check": "a"}],
                "attention_days": ["2026-12-10"],
                "streak": 1,
                "state": "observing",
            }
        ],
        "problems": [],
    },
    "observability-request": {
        "version": 1,
        "task": "TS-5",
        "day": "2026-12-09",
        "counts": [
            {"check": "a", "signal": "logs", "query": "q", "from": "f", "to": "t", "hash": "h"}
        ],
    },
    "observability-result": {
        "version": 1,
        "task": "TS-5",
        "day": "2026-12-09",
        "provider": "p",
        "counts": [{"check": "a", "hash": "h", "value": 2, "started": "s", "finished": "f"}],
        "failed": [{"check": "b", "reason": "r"}],
    },
    "database-request": {
        "version": 1,
        "database": "db",
        "sql": "select 1",
        "bounds": {"day": "2026-12-09"},
        "timeout_seconds": 30,
    },
    "database-result": {
        "version": 1,
        "database": "db",
        "value": 1.5,
        "started": "s",
        "finished": "f",
    },
}


@pytest.mark.parametrize("name", sorted(VALID))
def test_each_schema_accepts_a_valid_document(name):
    assert validate(VALID[name], name) == []


@pytest.mark.parametrize("name", sorted(VALID))
def test_each_schema_refuses_another_version(name):
    assert validate({**VALID[name], "version": 2}, name) == ["$.version: expected 1"]


def test_status_day_is_a_number():
    document = copy_status(day="3")
    assert validate(document, "observe-status") == ["$.plans[0].day: expected integer, got string"]


def test_status_plan_carries_first_day_not_switched_off():
    document = copy_status(switched_off="2026-12-08")
    del document["plans"][0]["first_day"]
    assert validate(document, "observe-status") == [
        "$.plans[0]: missing required key first_day",
        "$.plans[0].switched_off: unexpected key",
    ]


def copy_status(**changes):
    import copy

    document = copy.deepcopy(VALID["observe-status"])
    document["plans"][0].update(changes)
    return document


@pytest.mark.parametrize(
    ("schema", "text"),
    [
        ({"additionalProperties": True}, "additionalProperties"),
        ({"type": "str"}, "unknown type str"),
        ({"type": ["string", "nope"]}, "unknown type nope"),
        ({"required": "id"}, "required must be a list of strings"),
        ({"required": [1]}, "required must be a list of strings"),
        ({"enum": "ab"}, "enum must be a list"),
        ({"properties": {"a": {"enum": 1}}}, "enum must be a list"),
    ],
)
def test_check_refuses_malformed_schemas(schema, text):
    with pytest.raises(ValueError, match=text):
        check({}, schema)


def test_load_schema_returns_a_copy():
    first = load_schema("observe-plan")
    first["required"].append("x")
    assert "x" not in load_schema("observe-plan")["required"]


def test_bool_is_not_a_number_and_const_is_strict():
    assert check(True, {"type": "number"}) == ["$: expected number, got boolean"]
    assert check(1.0, {"const": 1}) == ["$: expected 1"]
    assert check(2, {"enum": ["a", 1]}) == ["$: expected one of a, 1"]
