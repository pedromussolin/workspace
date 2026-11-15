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
        "window": {"from": "2026-12-09T00:00:00-03:00", "to": "2026-12-10T00:00:00-03:00"},
        "hash": "abc",
        "times": "run",
        "by": None,
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
