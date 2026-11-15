import copy
import stat
import tomllib
from datetime import date
from decimal import Decimal

import pytest

from ws import observedef
from ws.observedef import Check, Invalid

TABLE = {
    "version": 1,
    "task": "TS-5",
    "job": "Job A",
    "switched_off": date(2026, 12, 8),
    "checks": [
        {"id": "a", "kind": "observability", "signal": "logs", "query": "q", "expect": "== 0"},
        {"id": "b", "kind": "database", "sql": "select 1", "expect": "<= 3"},
        {"id": "c", "kind": "manual", "question": "ok?"},
    ],
}


@pytest.fixture
def env(tmp_path, monkeypatch):
    monkeypatch.setenv("WS_DATA_DIR", str(tmp_path / "data"))
    monkeypatch.setenv("WS_CONFIG_DIR", str(tmp_path / "config"))
    return tmp_path


def mode(path):
    return stat.S_IMODE(path.stat().st_mode)


def test_plan_document_fills_defaults_and_dates():
    doc = observedef.plan_document(TABLE)
    assert doc["days"] == 5
    assert doc["timezone"] == "America/Sao_Paulo"
    assert doc["switched_off"] == "2026-12-08"
    assert doc["checks"][1]["database"] == "replica"
    assert "database" not in doc["checks"][0]
    assert "days" not in TABLE


def bad(mutate):
    table = copy.deepcopy(TABLE)
    mutate(table)
    return table


CASES = [
    (lambda t: t["checks"][0].pop("signal"), "checks[0].signal"),
    (lambda t: t["checks"][1].update(question="x"), "checks[1].question: not allowed for database"),
    (lambda t: t["checks"][2].update(expect="== 0"), "checks[2].expect: not allowed for manual"),
    (lambda t: t["checks"][1].update(id="a"), "checks[1].id: duplicate"),
    (lambda t: t["checks"][0].update(id="Bad_Id"), "checks[0].id"),
    (lambda t: t["checks"][0].update(expect=">= 1"), "checks[0].expect"),
    (lambda t: t.update(timezone="no/such_zone"), "timezone"),
    (lambda t: t.update(task="ts-1"), "task"),
    (lambda t: t.update(days=0), "days"),
]


@pytest.mark.parametrize(("mutate", "key"), CASES)
def test_parse_plan_kind_rules(mutate, key):
    document = observedef.plan_document(bad(mutate))
    with pytest.raises(Invalid) as caught:
        observedef.parse_plan(document, "plan.toml")
    assert str(caught.value).startswith(f"plan.toml: {key}")


def test_parse_plan_accepts_the_example():
    plan = observedef.parse_plan(observedef.plan_document(TABLE), "plan.toml")
    assert plan.switched_off == date(2026, 12, 8)
    assert [c.id for c in plan.checks] == ["a", "b", "c"]
    assert plan.checks[1].database == "replica"


def test_check_hash_ignores_id_and_label():
    base = Check(id="a", kind="observability", signal="logs", query="q", expect="== 0")
    same = Check(id="z", kind="observability", signal="logs", query="q", expect="== 0", label="L")
    assert observedef.check_hash(base) == observedef.check_hash(same)
    assert observedef.check_hash(base) != observedef.check_hash(
        Check(id="a", kind="observability", signal="logs", query="r", expect="== 0")
    )
    assert observedef.check_hash(base) != observedef.check_hash(
        Check(id="a", kind="observability", signal="logs", query="q", expect="<= 0")
    )
    assert len(observedef.check_hash(base)) == 12
    int(observedef.check_hash(base), 16)


def test_meets():
    assert observedef.meets(Decimal(0), "== 0")
    assert not observedef.meets(Decimal(1), "== 0")
    assert observedef.meets(Decimal(3), "<= 3")
    assert not observedef.meets(Decimal("3.5"), "<= 3")


def test_new_plan_text_round_trips():
    text = observedef.new_plan_text(
        "TS-5", 'Job "é" ção', date(2026, 12, 8), 5, "America/Sao_Paulo"
    )
    data = tomllib.loads(text)
    assert data["version"] == 1
    assert data["job"] == 'Job "é" ção'
    assert data["switched_off"] == date(2026, 12, 8)
    assert "checks" not in data


def test_write_new_is_private_and_refuses_overwrite(env):
    path = observedef.write_new("demo", "TS-5", "version = 1\n")
    assert path == observedef.plan_path("demo", "TS-5")
    root = env / "data" / "projects"
    for folder in (root, root / "demo", root / "demo" / "observations"):
        assert mode(folder) == 0o700
    assert mode(path) == 0o600
    with pytest.raises(Invalid) as caught:
        observedef.write_new("demo", "TS-5", "x")
    assert str(path) in str(caught.value)


def test_find_plan_none_one_two(env):
    with pytest.raises(Invalid, match="no observation plan for TS-5; run ws observe new TS-5"):
        observedef.find_plan("TS-5", None)
    observedef.write_new("demo", "TS-5", "a")
    assert observedef.find_plan("TS-5", None) == ("demo", observedef.plan_path("demo", "TS-5"))
    observedef.write_new("other", "TS-5", "a")
    with pytest.raises(Invalid, match="TS-5 has plans in demo, other; pass --project"):
        observedef.find_plan("TS-5", None)
    assert observedef.find_plan("TS-5", "other")[0] == "other"


def test_all_plans_sorted_and_filtered(env):
    for project, task in (("other", "TS-6"), ("demo", "TS-6"), ("demo", "TS-5")):
        observedef.write_new(project, task, "a")
    listed = observedef.all_plans(None)
    assert [(p, path.stem) for p, path in listed] == [
        ("demo", "TS-5"),
        ("demo", "TS-6"),
        ("other", "TS-6"),
    ]
    assert [p for p, _ in observedef.all_plans("other")] == ["other"]


def test_tighten_restores_modes(env):
    path = observedef.write_new("demo", "TS-5", "a")
    results = path.with_name("TS-5.results.jsonl")
    results.write_text("")
    path.chmod(0o644)
    results.chmod(0o644)
    messages = observedef.tighten(path)
    assert f"{path}: mode 644 set to 600" in messages
    assert f"{results}: mode 644 set to 600" in messages
    assert mode(path) == 0o600
    assert mode(results) == 0o600
    assert observedef.tighten(path) == []


def test_load_plan_names_the_path(env):
    path = observedef.write_new("demo", "TS-5", "version = [")
    with pytest.raises(Invalid) as caught:
        observedef.load_plan(path)
    assert str(path) in str(caught.value)
