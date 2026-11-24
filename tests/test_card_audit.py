import json
from datetime import date
from types import SimpleNamespace

import pytest
from fake_tracker import FakeTracker, make_card
from item_helpers import ANA, CONFIG, ME

from ws import cardaudit, cardpolicy
from ws.carddraft import parse_draft
from ws.cli import main
from ws.config import data_dir
from ws.contracts import validate
from ws.taskmodel import Status
from ws.tracker.errors import TrackerError

COMPANY = """\
version = 1

[title]
format = "subgroup"

[create]
require = ["estimate", "due", "categories"]

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

[links.bug]
caused_by = "suggest"
"""
PROJECT = """\
version = 1

[title]
format = "epic_prefix"
"""
FULL = "## Contexto\nPor que existe.\n\n## Pronto quando\n- Feito.\n"
CARD_TABLE = '\n[card]\npolicy = "acme-like"\n'
OTHER = "acc-other"


@pytest.fixture
def world(tmp_path, ws_config, monkeypatch):
    root = tmp_path / "repo"
    (root / "projects" / "demo").mkdir(parents=True)
    (root / "projects" / "demo" / "project.toml").write_text('epics = ["TS-200"]\n')
    monkeypatch.setenv("WS_REPO_ROOT", str(root))
    (ws_config / "card-policies").mkdir()
    (ws_config / "card-policies" / "acme-like.toml").write_text(COMPANY, encoding="utf-8")
    (ws_config / "config.toml").write_text(CONFIG + CARD_TABLE, encoding="utf-8")
    return SimpleNamespace(root=root, config=ws_config)


def good(ref="TS-1", **fields):
    values = {
        "title": "[group] - done well",
        "status": Status.IN_PROGRESS,
        "sprint": "Sprint 55",
        "due": date(2026, 11, 27),
        "labels": ("planned", "SMALL"),
        "estimate_minutes": 120,
        "start": date(2026, 11, 20),
        "spent_minutes": 30,
    }
    values.update(fields)
    return make_card(ref, **values)


def broken(ref="TS-2", **fields):
    values = {"title": "[FRONT] no group", "sprint": "Sprint 55"}
    values.update(fields)
    return make_card(ref, **values)


EPIC = make_card("TS-100", title="[FRONT] Epic", type="epic", level=1, parent=None, sprint=None)
PROJECT_EPIC = make_card(
    "TS-200", title="[BACK] Epic", type="epic", level=1, parent=None, sprint=None
)


def cards():
    return [
        EPIC,
        PROJECT_EPIC,
        good("TS-1"),
        broken("TS-2"),
        good("TS-3", labels=("planned", "SMALL"), estimate_minutes=600),
        good("TS-4", status=Status.DONE, start=None, spent_minutes=None),
        make_card(
            "TS-5",
            type="bug",
            title="[group] - bug",
            assignee="acc-ana",
            reporter=OTHER,
            sprint="Sprint 55",
            due=date(2026, 11, 27),
            labels=("planned", "SMALL"),
            estimate_minutes=600,
        ),
        good("TS-6", status=Status.CANCELLED, labels=()),
        good("TS-7", assignee="acc-ana", reporter="acc-me", sprint="Sprint 56"),
    ]


DESCRIPTIONS = {
    "TS-1": FULL,
    "TS-3": FULL,
    "TS-4": FULL,
    "TS-5": FULL,
    "TS-7": FULL,
}


@pytest.fixture
def tracker(world, monkeypatch):
    def install(items=None, **options):
        options.setdefault("descriptions", DESCRIPTIONS)
        options.setdefault("names", {"acc-ana": "Ana Example"})
        fake = FakeTracker(cards() if items is None else items, **options)
        monkeypatch.setattr("ws.tracker.port.open_tracker", lambda: fake)
        return fake

    return install


def audit(capsys, *argv):
    code = main(["card", "audit", *argv])
    out = capsys.readouterr()
    return code, json.loads(out.out) if out.out.strip() else None, out.err


def entry(document, ref):
    (found,) = [item for item in document["cards"] if item["ref"] == ref]
    return found


def rules(document, ref):
    return sorted(gap["rule"] for gap in entry(document, ref)["gaps"])


def test_a_broken_card_is_flagged_for_every_rule_it_breaks(tracker, capsys):
    tracker()

    code, document, _ = audit(capsys)

    assert code == 0
    assert rules(document, "TS-2") == [
        "categories.label.required",
        "categories.tag.required",
        "create.require.due",
        "create.require.estimate",
        "sections.required",
        "sections.required",
        "title.format",
    ]
    details = [gap["detail"] for gap in entry(document, "TS-2")["gaps"]]
    assert "title must be '[group] - text'" in details
    assert "section 'Contexto' is missing or empty" in details


def test_a_well_filled_card_has_no_gaps(tracker, capsys):
    tracker()

    code, document, _ = audit(capsys)

    assert code == 0
    assert rules(document, "TS-2") != []
    assert entry(document, "TS-1") == {
        "ref": "TS-1",
        "title": "[group] - done well",
        "assignee": "acc-me",
        "writable": True,
        "gaps": [],
    }


def test_the_output_follows_the_card_audit_contract_and_changes_nothing(tracker, capsys):
    fake = tracker()

    _, document, _ = audit(capsys)

    assert validate(document, "card-audit") == []
    assert document["$schema"] == "card-audit"
    assert fake.sent == []
    assert "drafts" not in document


def test_the_summary_counts_cards_gaps_and_rules(tracker, capsys):
    tracker()

    _, document, _ = audit(capsys)

    refs = [item["ref"] for item in document["cards"]]
    assert refs == ["TS-1", "TS-2", "TS-3", "TS-4"]
    assert document["summary"] == {
        "cards": 4,
        "with_gaps": 3,
        "by_rule": {
            "categories.label.required": 1,
            "categories.tag.derive": 1,
            "categories.tag.required": 1,
            "create.require.due": 1,
            "create.require.estimate": 1,
            "finish.require.start": 1,
            "finish.require.time_spent": 1,
            "sections.required": 2,
            "title.format": 1,
        },
    }


def test_a_category_that_contradicts_the_estimate_carries_the_computed_value(tracker, capsys):
    tracker()

    _, document, _ = audit(capsys)

    (gap,) = entry(document, "TS-3")["gaps"]
    assert gap["rule"] == "categories.tag.derive"
    assert gap["fix"] == {"value": "BIG"}
    required = [g for g in entry(document, "TS-2")["gaps"] if g["field"] == "title"]
    assert required[0]["fix"] == {"needs": "input"}


def test_a_done_card_gets_the_finish_gaps_and_an_open_one_does_not(tracker, capsys):
    tracker()

    _, document, _ = audit(capsys)

    assert rules(document, "TS-4") == ["finish.require.start", "finish.require.time_spent"]
    assert not any(rule.startswith("finish") for rule in rules(document, "TS-2"))


def test_a_cancelled_card_is_left_out(tracker, capsys):
    tracker()

    _, document, _ = audit(capsys)

    assert "TS-6" not in [item["ref"] for item in document["cards"]]


def test_an_epic_in_the_selection_is_left_out(tracker, capsys):
    tracker()

    code, document, _ = audit(capsys, "--keys", "TS-100,TS-1")

    assert code == 0
    assert [item["ref"] for item in document["cards"]] == ["TS-1"]


def test_a_bug_without_a_cause_link_gets_the_suggestion(tracker, capsys):
    tracker()

    code, document, _ = audit(capsys, "--keys", "TS-5")

    assert code == 0
    (gap,) = [g for g in entry(document, "TS-5")["gaps"] if g["rule"] == "links.bug.caused_by"]
    assert gap["severity"] == "suggestion"
    assert gap["fix"] == {"needs": "input"}


def test_writable_is_the_assignee_or_the_reporter(tracker, capsys):
    tracker()

    _, document, _ = audit(capsys, "--keys", "TS-1,TS-5,TS-7")

    assert entry(document, "TS-1")["writable"] is True
    assert entry(document, "TS-7")["writable"] is True
    assert entry(document, "TS-7")["assignee"] == "Ana Example"
    assert entry(document, "TS-5")["writable"] is False


def test_keys_audit_exactly_those_cards(tracker, capsys):
    tracker()

    _, document, _ = audit(capsys, "--keys", "TS-3, TS-2,TS-3")

    assert [item["ref"] for item in document["cards"]] == ["TS-2", "TS-3"]


def test_keys_with_a_card_outside_the_project_is_exit_1(tracker, capsys):
    tracker()

    code, document, err = audit(capsys, "--keys", "TS-2,TS-999")

    assert (code, document) == (1, None)
    assert "TS-999" in err


@pytest.mark.parametrize(
    "argv",
    [
        ["--keys", "TS-1", "--sprint", "active"],
        ["--keys", "TS-1", "--who", "me"],
        ["--keys", "not a ref"],
        ["--keys", ","],
        ["--who", "ana"],
    ],
)
def test_arguments_that_do_not_fit_are_exit_1(tracker, capsys, argv):
    fake = tracker()

    code, document, err = audit(capsys, *argv)

    assert (code, document) == (1, None)
    assert err.startswith("ws card audit: ")
    assert fake.reads == []


def test_who_takes_a_colleague_by_dev_id_and_can_repeat(tracker, capsys):
    tracker()

    _, only_ana, _ = audit(capsys, "--who", ANA)
    _, both, _ = audit(capsys, "--who", "me", "--who", ANA)

    assert [item["ref"] for item in only_ana["cards"]] == ["TS-5"]
    assert [item["ref"] for item in both["cards"]] == ["TS-1", "TS-2", "TS-3", "TS-4", "TS-5"]


def test_who_with_my_own_dev_id_is_me(tracker, capsys):
    tracker()

    _, document, _ = audit(capsys, "--who", ME)

    assert [item["ref"] for item in document["cards"]] == ["TS-1", "TS-2", "TS-3", "TS-4"]


def test_a_dev_id_the_config_does_not_know_is_a_setup_error_with_the_hint(tracker, capsys):
    tracker()

    code, document, err = audit(capsys, "--who", "dev-0123456789")

    assert (code, document) == (2, None)
    assert "unknown person" in err
    assert "ws people add" in err


def test_the_sprint_is_active_by_default_and_can_be_next_or_a_name(tracker, capsys):
    tracker([good("TS-1"), good("TS-7", sprint="Sprint 56"), good("TS-8", sprint="Sprint 57")])

    _, default, _ = audit(capsys)
    _, upcoming, _ = audit(capsys, "--sprint", "next")
    _, named, _ = audit(capsys, "--sprint", "Sprint 57")

    assert [item["ref"] for item in default["cards"]] == ["TS-1"]
    assert [item["ref"] for item in upcoming["cards"]] == ["TS-7"]
    assert [item["ref"] for item in named["cards"]] == ["TS-8"]


def test_the_project_policy_of_the_epic_wins_and_each_policy_loads_once(
    world, tracker, capsys, monkeypatch
):
    (world.root / "projects" / "demo" / "card-policy.toml").write_text(PROJECT, encoding="utf-8")
    tracker(
        [
            PROJECT_EPIC,
            EPIC,
            good("TS-1", title="[BACK] fine", parent="TS-200"),
            good("TS-2", title="[BACK] fine", parent="TS-100"),
            good("TS-3", title="[FRONT] wrong prefix", parent="TS-200"),
        ],
        descriptions={ref: FULL for ref in ("TS-1", "TS-2", "TS-3")},
    )
    loaded = []
    real = cardpolicy.load

    def counting(config, project, root):
        loaded.append(project)
        return real(config, project, root)

    monkeypatch.setattr(cardpolicy, "load", counting)

    _, document, _ = audit(capsys)

    assert rules(document, "TS-1") == []
    assert rules(document, "TS-2") == ["title.format"]
    assert rules(document, "TS-3") == ["title.format"]
    assert "[BACK]" in entry(document, "TS-3")["gaps"][0]["detail"]
    assert sorted(loaded, key=str) == [None, "demo"]


def test_sections_come_from_the_description_headings(tracker, capsys):
    tracker(descriptions={"TS-1": "## Contexto\ntexto\n\n## Pronto quando\n\n"})

    _, document, _ = audit(capsys, "--keys", "TS-1")

    (gap,) = entry(document, "TS-1")["gaps"]
    assert gap["detail"] == "section 'Pronto quando' is missing or empty"


def test_parse_sections_ignores_headings_inside_code_and_joins_repeats():
    text = "intro\n## A\none\n```\n## B\n```\n## A\ntwo\n"

    sections = cardaudit.parse_sections(text)

    assert list(sections) == ["A"]
    assert "one" in sections["A"] and "## B" in sections["A"] and "two" in sections["A"]
    assert cardaudit.parse_sections(None) == {}


def drafts_dir(name="audit-2026-11-24"):
    return data_dir() / "cards" / "drafts" / name


def test_drafts_hold_the_computed_labels_of_writable_cards_only(tracker, capsys):
    fake = tracker()
    folder = drafts_dir()

    code, document, _ = audit(
        capsys, "--who", "me", "--who", ANA, "--sprint", "Sprint 55", "--drafts", str(folder)
    )

    assert code == 0
    assert sorted(path.name for path in folder.iterdir()) == ["TS-3.md"]
    draft = parse_draft((folder / "TS-3.md").read_bytes())
    assert draft.op == "edit"
    assert draft.values["key"] == "TS-3"
    assert draft.values["add_labels"] == ["BIG"]
    assert draft.values["remove_labels"] == ["SMALL"]
    assert (folder / "TS-3.md").stat().st_mode & 0o777 == 0o600
    assert document["drafts"]["folder"] == str(folder)
    assert document["drafts"]["count"] == 1
    assert document["drafts"]["not_writable"] == ["TS-5"]
    assert validate(document, "card-audit") == []
    assert fake.sent == []


def test_drafts_list_every_gap_that_needs_input_of_writable_cards(tracker, capsys):
    tracker()

    _, document, _ = audit(capsys, "--drafts", str(drafts_dir()))

    need = document["drafts"]["need_input"]
    assert {(item["ref"], item["rule"]) for item in need} == {
        ("TS-2", "title.format"),
        ("TS-2", "sections.required"),
        ("TS-2", "create.require.estimate"),
        ("TS-2", "create.require.due"),
        ("TS-2", "categories.label.required"),
        ("TS-2", "categories.tag.required"),
        ("TS-4", "finish.require.start"),
        ("TS-4", "finish.require.time_spent"),
    }
    assert all(set(item) == {"ref", "rule", "field", "detail"} for item in need)
    assert {item["field"] for item in need if item["ref"] == "TS-4"} == {"start", "time_spent"}


def test_a_required_category_with_a_computed_value_is_added_without_a_removal(tracker, capsys):
    tracker([good("TS-1", labels=("planned",), estimate_minutes=60)], descriptions=DESCRIPTIONS)
    folder = drafts_dir()

    _, document, _ = audit(capsys, "--drafts", str(folder))

    draft = parse_draft((folder / "TS-1.md").read_bytes())
    assert draft.values["add_labels"] == ["SMALL"]
    assert "remove_labels" not in draft.values
    assert document["drafts"]["need_input"] == []


def test_drafts_refuse_a_folder_that_is_not_empty_and_read_nothing(tracker, capsys):
    fake = tracker()
    folder = drafts_dir()
    folder.mkdir(parents=True)
    (folder / "keep.md").write_text("x", encoding="utf-8")

    code, document, err = audit(capsys, "--drafts", str(folder))

    assert (code, document) == (1, None)
    assert "not empty" in err
    assert fake.reads == []
    assert [path.name for path in folder.iterdir()] == ["keep.md"]


def test_drafts_accept_an_existing_empty_folder(tracker, capsys):
    tracker()
    folder = drafts_dir()
    folder.mkdir(parents=True)

    code, document, _ = audit(capsys, "--drafts", str(folder))

    assert code == 0
    assert document["drafts"]["count"] == 1


@pytest.mark.parametrize("where", ["outside", "root", "file"])
def test_drafts_refuse_a_folder_a_preview_could_not_read(tracker, capsys, tmp_path, where):
    tracker()
    target = {
        "outside": tmp_path / "elsewhere",
        "root": data_dir() / "cards" / "drafts",
        "file": drafts_dir("a-file"),
    }[where]
    if where == "file":
        target.parent.mkdir(parents=True)
        target.write_text("x", encoding="utf-8")

    code, document, err = audit(capsys, "--drafts", str(target))

    assert (code, document) == (1, None)
    assert err.startswith("ws card audit: ")
    assert not (tmp_path / "elsewhere").exists()


def test_a_failed_audit_leaves_no_drafts_folder(tracker, capsys):
    tracker()
    folder = drafts_dir()

    code, _, _ = audit(capsys, "--who", "dev-0123456789", "--drafts", str(folder))

    assert code == 2
    assert not folder.exists()


def test_a_missing_company_policy_file_is_a_setup_error(tracker, capsys, world):
    tracker()
    (world.config / "card-policies" / "acme-like.toml").unlink()

    code, document, err = audit(capsys)

    assert (code, document) == (2, None)
    assert "card policy file" in err


def test_a_missing_config_is_a_setup_error(tracker, capsys, world):
    tracker()
    (world.config / "config.toml").unlink()

    code, document, err = audit(capsys)

    assert (code, document) == (2, None)
    assert "config.toml" in err


def test_an_identity_less_config_is_a_setup_error(tracker, capsys, world):
    tracker()
    (world.config / "config.toml").write_text(
        CONFIG.replace('email = "dev@example.com"\n', ""), encoding="utf-8"
    )

    code, _, err = audit(capsys)

    assert code == 2
    assert "identity" in err


class Refusing(FakeTracker):
    def cards(self, query):
        raise TrackerError("the tracker refused the search")


def test_a_tracker_that_refuses_is_exit_3(world, monkeypatch, capsys):
    fake = Refusing(cards())
    monkeypatch.setattr("ws.tracker.port.open_tracker", lambda: fake)

    code, document, err = audit(capsys)

    assert (code, document) == (3, None)
    assert "refused" in err


def test_a_malformed_tracker_answer_is_exit_3(world, monkeypatch, capsys):
    class Odd(FakeTracker):
        def description(self, ref):
            raise KeyError("fields")

    fake = Odd(cards(), descriptions=DESCRIPTIONS)
    monkeypatch.setattr("ws.tracker.port.open_tracker", lambda: fake)

    code, _, err = audit(capsys)

    assert code == 3
    assert "unexpected answer" in err
