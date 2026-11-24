import json
import tomllib
from importlib import resources

import pytest

from ws.cardpolicy import Policy, evaluate, layer_problems, load, project_for
from ws.contracts import validate
from ws.tracker import vocab
from ws.userconfig import ConfigInvalid, ConfigMissing, UserConfig, load_config

COMPANY = """\
version = 1

[title]
format = "subgroup"

[sections.bug]
required = ["Problema", "Pronto quando"]
optional = []

[create]
require = ["epic", "estimate", "categories"]

[categories.label]
values = ["planned", "planned-team", "intruder-ops"]
required = true

[categories.tag]
values = ["BIG", "SMALL", "NEW"]
required = true
skip_when = ["planned-team"]

[categories.tag.derive]
from = "estimate"
threshold_hours = 6
above = "BIG"
at_most = "SMALL"
keep = ["NEW"]

[epic]
skip_when = ["planned-team"]

[finish]
require = ["start", "time_spent"]

[links.bug]
caused_by = "suggest"
"""


@pytest.fixture
def config_dir(tmp_path, monkeypatch):
    folder = tmp_path / "ws-config"
    (folder / "card-policies").mkdir(parents=True)
    monkeypatch.setenv("WS_CONFIG_DIR", str(folder))
    return folder


@pytest.fixture
def repo(tmp_path):
    root = tmp_path / "repo"
    (root / "projects" / "alpha").mkdir(parents=True)
    (root / "projects" / "beta").mkdir()
    (root / "projects" / "alpha" / "project.toml").write_text('epics = ["TS-1", "TS-2"]\n')
    (root / "projects" / "beta" / "project.toml").write_text('epics = ["TS-3"]\n')
    return root


def user_config(name=None):
    return UserConfig(standup=None, card_policy=name)


def company(config_dir, text=COMPANY, name="acme-like"):
    (config_dir / "card-policies" / f"{name}.toml").write_text(text, encoding="utf-8")
    return user_config(name)


def project_layer(repo, text, slug="alpha"):
    (repo / "projects" / slug / "card-policy.toml").write_text(text, encoding="utf-8")


def default_policy(repo):
    return load(None, None, repo)


def card(**changes):
    document = {
        "type": "task",
        "title": "[group] - text",
        "epic": "TS-1",
        "epic_prefix": None,
        "labels": [],
        "estimate_minutes": 120,
        "spent_minutes": None,
        "start": None,
        "due": None,
        "sprint": None,
        "assignee": "dev-0000000001",
        "reporter": "dev-0000000001",
        "sections": {"Contexto": "x", "Pronto quando": "y"},
        "status": "todo",
        "links": [],
    }
    document.update(changes)
    return document


def rules(gaps):
    return [gap["rule"] for gap in gaps]


@pytest.fixture
def fake(config_dir, repo):
    return load(company(config_dir), None, repo)


def complete_card(**changes):
    return card(**{"labels": ["planned", "SMALL"], **changes})


def test_default_sections_equal_the_vocabulary():
    default = tomllib.loads(
        (resources.files("ws") / "data" / "card-policy" / "default.toml").read_text("utf-8")
    )
    assert sections_drift(default["sections"], vocab._SECTIONS) == []


def sections_drift(policy_sections, expected):
    drift = []
    for type_, headings in expected.items():
        found = policy_sections.get(type_, {}).get("required")
        if found != list(headings):
            drift.append(f"{type_}: {found} != {list(headings)}")
    for type_ in policy_sections:
        if type_ not in expected:
            drift.append(f"{type_}: not in the vocabulary")
    return drift


def test_the_drift_scan_flags_a_broken_sample():
    broken = {"task": {"required": ["Contexto"]}, "story": {"required": []}}
    drift = sections_drift(broken, vocab._SECTIONS)
    assert any(line.startswith("task:") for line in drift)
    assert any(line.startswith("bug:") for line in drift)
    assert "story: not in the vocabulary" in drift


def test_default_policy_is_todays_behaviour(repo):
    policy = default_policy(repo)

    assert validate({**policy.data}, "card-policy") == []
    assert policy.data["title"] == {"format": "epic_prefix"}
    assert policy.data["create"] == {"require": ["epic"], "due_with_sprint": True}
    assert policy.data["finish"] == {"require": []}
    assert policy.data["links"] == {"bug": {"caused_by": "off"}}
    assert policy.data["estimate"] == {"padding_percent": 0, "unplanned_labels": []}
    assert "categories" not in policy.data
    assert set(policy.sources.values()) == {"default"}


def test_default_optional_sections_are_the_two_of_the_card_rules(repo):
    sections = default_policy(repo).data["sections"]
    for type_ in vocab.CARD_TYPES:
        assert sections[type_]["optional"] == ["Desenho combinado", "A fazer antes de implementar"]
    assert sections["epic"]["optional"] == []


def test_company_layer_merges_key_by_key_and_replaces_lists_whole(config_dir, repo):
    policy = load(company(config_dir), None, repo)

    assert policy.data["title"]["format"] == "subgroup"
    assert policy.data["create"] == {
        "require": ["epic", "estimate", "categories"],
        "due_with_sprint": True,
    }
    assert policy.data["sections"]["bug"] == {
        "required": ["Problema", "Pronto quando"],
        "optional": [],
    }
    assert policy.data["sections"]["task"]["required"] == ["Contexto", "Pronto quando"]
    assert policy.data["finish"]["require"] == ["start", "time_spent"]


def test_sources_name_the_layer_of_each_top_level_key(config_dir, repo):
    project_layer(repo, 'version = 1\n[finish]\nrequire = ["start"]\n')
    policy = load(company(config_dir), "alpha", repo)

    assert policy.sources["version"] == "default"
    assert policy.sources["estimate"] == "default"
    assert policy.sources["title"] == "company"
    assert policy.sources["categories"] == "company"
    assert policy.sources["finish"] == "project"
    assert policy.to_dict()["sources"] == policy.sources


def test_project_wins_over_company_and_over_default(config_dir, repo):
    project_layer(
        repo,
        'version = 1\n[title]\nformat = "epic_prefix"\n[categories.tag]\nrequired = false\n'
        '[create]\nrequire = ["epic"]\n',
    )
    policy = load(company(config_dir), "alpha", repo)

    assert policy.data["title"]["format"] == "epic_prefix"
    assert policy.data["create"]["require"] == ["epic"]
    assert policy.data["categories"]["tag"]["required"] is False
    assert policy.data["categories"]["tag"]["values"] == ["BIG", "SMALL", "NEW"]
    assert policy.data["categories"]["tag"]["derive"]["threshold_hours"] == 6


def test_a_project_without_a_file_or_another_project_adds_nothing(config_dir, repo):
    project_layer(repo, 'version = 1\n[title]\nformat = "epic_prefix"\n')

    assert load(company(config_dir), "beta", repo).data["title"]["format"] == "subgroup"
    assert load(company(config_dir), None, repo).data["title"]["format"] == "subgroup"


def test_to_json_prints_the_document_with_sources(config_dir, repo):
    policy = load(company(config_dir), None, repo)
    document = json.loads(policy.to_json())

    sources = document.pop("sources")
    assert validate(document, "card-policy") == []
    assert sources["title"] == "company"
    assert isinstance(policy, Policy)


def test_a_configured_name_without_a_file_is_a_setup_error(config_dir, repo):
    with pytest.raises(ConfigMissing) as error:
        load(user_config("nowhere"), None, repo)

    assert str(config_dir / "card-policies" / "nowhere.toml") in str(error.value)


def test_a_policy_name_cannot_walk_out_of_the_folder(config_dir, repo):
    with pytest.raises(ConfigInvalid):
        load(user_config("../x"), None, repo)


def test_an_invalid_layer_names_its_file_and_the_problems(config_dir, repo):
    config = company(config_dir, 'version = 1\n[title]\nformat = "other"\n[nope]\nx = 1\n')

    with pytest.raises(ConfigInvalid) as error:
        load(config, None, repo)

    message = str(error.value)
    assert str(config_dir / "card-policies" / "acme-like.toml") in message
    assert "$.title.format: expected one of epic_prefix, subgroup" in message
    assert "$.nope: unexpected key" in message


def test_a_layer_that_is_not_toml_is_invalid(config_dir, repo):
    with pytest.raises(ConfigInvalid):
        load(company(config_dir, "version = ="), None, repo)


def test_a_project_layer_is_validated_alone(config_dir, repo):
    project_layer(repo, "[title]\nformat = 'subgroup'\n")

    with pytest.raises(ConfigInvalid, match="card-policy.toml.*missing required key version"):
        load(None, "alpha", repo)


@pytest.mark.parametrize(
    ("text", "problem"),
    [
        ("version = 2", "$.version: expected 1"),
        ("version = 1\n[create]\nrequire = ['mood']", "$.create.require[0]: expected one of"),
        ("version = 1\n[finish]\nrequire = ['end']", "$.finish.require[0]: expected one of"),
        ("version = 1\n[links.bug]\ncaused_by = 'on'", "$.links.bug.caused_by: expected one of"),
        ("version = 1\n[links.task]\nx = 1", "$.links.task: unexpected key"),
        ("version = 1\n[sections.story]\nrequired = []", "$.sections.story: unexpected key"),
        ("version = 1\n[sections.task]\nrequires = []", "$.sections.task.requires: unexpected"),
        ("version = 1\n[estimate]\npadding_percent = -1", "padding_percent: must not be negative"),
        (
            "version = 1\n[estimate]\nunplanned_labels = ['a b']",
            "unplanned_labels: 'a b' must be text without whitespace",
        ),
        ("version = 1\n[estimate]\nunplanned_labels = 'x'", "unplanned_labels: expected array"),
        ("version = 1\n[categories.a]\nvalues = []", "$.categories.a.values: must not be empty"),
        (
            "version = 1\n[categories.a]\nvalues = ['x y']",
            "'x y' must be text without whitespace",
        ),
        ("version = 1\n[categories.a]\nvalues = ['x', 'x']", "values must be unique"),
        (
            "version = 1\n[categories.a]\nrequired = 'yes'",
            "$.categories.a.required: expected boolean",
        ),
        ("version = 1\n[categories.a]\nextra = 1", "$.categories.a.extra: unexpected key"),
        (
            "version = 1\n[categories.a.derive]\nthreshold_hours = 0",
            "threshold_hours: must be greater than 0",
        ),
        (
            "version = 1\n[categories.a.derive]\nfrom = 'spent'",
            "$.categories.a.derive.from: expected one of estimate",
        ),
    ],
)
def test_layer_refusals(text, problem):
    problems = layer_problems(tomllib.loads(text))

    assert any(problem in line for line in problems), problems


def test_the_merged_policy_is_validated_as_a_whole(config_dir, repo):
    text = (
        "version = 1\n[categories.tag]\nvalues = ['A', 'B']\n"
        "[categories.tag.derive]\nfrom = 'estimate'\nthreshold_hours = 4\nabove = 'A'\n"
        "at_most = 'Z'\nkeep = ['Q']\n[categories.other]\nrequired = true\n"
        "[categories.third]\nvalues = ['A']\n"
    )

    with pytest.raises(ConfigInvalid) as error:
        load(company(config_dir, text), None, repo)

    message = str(error.value)
    assert "merged card policy (default, company)" in message
    assert "$.categories.other: missing required key values" in message
    assert "$.categories.tag.derive.at_most: 'Z' is not in values" in message
    assert "$.categories.tag.derive.keep: 'Q' is not in values" in message
    assert "'A' is also in group tag" in message


def test_a_partial_derive_is_completed_by_a_later_layer(config_dir, repo):
    project_layer(repo, "version = 1\n[categories.tag.derive]\nthreshold_hours = 8\n")

    policy = load(company(config_dir), "alpha", repo)

    assert policy.data["categories"]["tag"]["derive"]["threshold_hours"] == 8
    assert policy.data["categories"]["tag"]["derive"]["above"] == "BIG"


def test_derive_without_its_fields_is_refused_once_merged(config_dir, repo):
    text = (
        "version = 1\n[categories.tag]\nvalues = ['A']\n"
        "[categories.tag.derive]\nfrom = 'estimate'\n"
    )

    with pytest.raises(ConfigInvalid, match="derive: missing required key threshold_hours"):
        load(company(config_dir, text), None, repo)


def test_config_reads_the_policy_name(tmp_path, monkeypatch):
    folder = tmp_path / "cfg"
    folder.mkdir()
    monkeypatch.setenv("WS_CONFIG_DIR", str(folder))
    monkeypatch.setenv("HOME", str(tmp_path))
    (folder / "config.toml").write_text('[card]\npolicy = "acme-like"\n', encoding="utf-8")

    assert load_config().card_policy == "acme-like"

    (folder / "config.toml").write_text("[identity]\nemail = 'a@example.com'\n", encoding="utf-8")
    assert load_config().card_policy is None

    (folder / "config.toml").write_text("[card]\npolicy = 3\n", encoding="utf-8")
    with pytest.raises(ConfigInvalid, match="card.policy"):
        load_config()

    (folder / "config.toml").write_text('[card]\npolicy = "../up"\n', encoding="utf-8")
    with pytest.raises(ConfigInvalid, match="card.policy"):
        load_config()


def test_project_of_an_item_path(repo):
    assert project_for("projects/alpha/tasks/1-x.md", None, repo) == "alpha"
    assert project_for(str(repo / "projects" / "beta" / "tasks" / "1-x.md"), None, repo) == "beta"
    assert project_for("projects/alpha/tasks/1-x.md", "TS-3", repo) == "alpha"


def test_project_of_an_epic_when_there_is_no_item(repo):
    assert project_for(None, "TS-3", repo) == "beta"
    assert project_for("docs/elsewhere.md", "TS-2", repo) == "alpha"
    assert project_for(None, "TS-99", repo) is None
    assert project_for(None, None, repo) is None


def test_project_of_an_epic_ignores_a_broken_project_toml(repo):
    (repo / "projects" / "alpha" / "project.toml").write_text("epics = [")

    assert project_for(None, "TS-3", repo) == "beta"
    assert project_for(None, "TS-1", repo) is None


def test_unknown_stage_is_refused(repo):
    with pytest.raises(ValueError, match="unknown stage"):
        evaluate(default_policy(repo), card(), "publish")


def test_default_accepts_a_complete_card(repo):
    assert evaluate(default_policy(repo), card(), "create") == []


def test_default_title_must_carry_the_epic_prefix(repo):
    policy = default_policy(repo)

    gaps = evaluate(policy, card(title="text", epic_prefix="FRONT"), "create")
    assert rules(gaps) == ["title.format"]
    assert gaps[0] == {
        "rule": "title.format",
        "field": "title",
        "detail": "title must start with '[FRONT] '",
        "fix": {"needs": "input"},
        "severity": "required",
    }
    assert evaluate(policy, card(title="[FRONT] text", epic_prefix="FRONT"), "create") == []
    assert evaluate(policy, card(title="anything", epic_prefix=None), "create") == []


@pytest.mark.parametrize(
    ("title", "ok"),
    [
        ("[ops] - text", True),
        ("[a b c] - x", True),
        ("[ops] text", False),
        ("[ops]- text", False),
        ("[] - text", False),
        ("[[ops]] - text", False),
        ("[" + "x" * 61 + "] - text", False),
        ("[" + "x" * 60 + "] - text", True),
        ("[ops] - ", False),
        ("ops - text", False),
    ],
)
def test_subgroup_title(fake, title, ok):
    gaps = evaluate(fake, complete_card(title=title), "create")

    assert (rules(gaps) == []) is ok, gaps


def test_required_sections_must_be_present_and_not_empty(repo):
    policy = default_policy(repo)
    bug = card(type="bug", sections={"Contexto": "x", "Pronto quando": "  \n", "Evidência": "log"})

    gaps = evaluate(policy, bug, "create")

    assert rules(gaps) == ["sections.required", "sections.required"]
    assert [g["detail"] for g in gaps] == [
        "section 'Pronto quando' is missing or empty",
        "section 'Como reproduzir' is missing or empty",
    ]
    assert (
        evaluate(policy, card(type="epic", epic=None, sections={"Contexto": "x"}), "create") == []
    )


def test_the_company_bug_sections_replace_the_default(fake):
    ok = complete_card(type="bug", sections={"Problema": "p", "Pronto quando": "q"})
    old = complete_card(type="bug", sections={"Contexto": "p", "Pronto quando": "q"})

    assert "sections.required" not in rules(evaluate(fake, ok, "create"))
    assert [
        g["detail"] for g in evaluate(fake, old, "create") if g["rule"] == "sections.required"
    ] == ["section 'Problema' is missing or empty"]


def test_create_require_fields(config_dir, repo):
    text = 'version = 1\n[create]\nrequire = ["epic", "due", "estimate", "assignee", "reporter"]\n'
    policy = load(company(config_dir, text), None, repo)
    empty = card(epic=None, due=None, estimate_minutes=None, assignee=None, reporter=None)

    gaps = evaluate(policy, empty, "create")

    assert [g["field"] for g in gaps] == ["epic", "due", "estimate", "assignee", "reporter"]
    assert rules(gaps)[0] == "create.require.epic"
    assert evaluate(policy, card(due="2026-12-01", estimate_minutes=30), "create") == []
    assert [
        g["field"] for g in evaluate(policy, card(estimate_minutes=0, due="2026-12-01"), "create")
    ] == ["estimate"]


def test_epic_is_required_only_for_card_types(repo):
    policy = default_policy(repo)

    assert rules(evaluate(policy, card(epic=None), "create")) == ["create.require.epic"]
    for type_ in vocab.UPPER_TYPES:
        upper = card(type=type_, epic=None, sections={"Contexto": "x"})
        assert evaluate(policy, upper, "create") == []


def test_a_due_date_is_required_with_a_sprint(repo):
    policy = default_policy(repo)

    gaps = evaluate(policy, card(sprint="Sprint 1"), "create")
    assert rules(gaps) == ["create.due_with_sprint"]
    assert gaps[0]["field"] == "due"
    assert evaluate(policy, card(sprint="Sprint 1", due="2026-12-01"), "create") == []
    assert evaluate(policy, card(sprint=None), "create") == []


def test_due_with_sprint_can_be_switched_off(config_dir, repo):
    text = "version = 1\n[create]\ndue_with_sprint = false\n"
    policy = load(company(config_dir, text), None, repo)

    assert evaluate(policy, card(sprint="Sprint 1"), "create") == []


def test_due_required_and_sprint_report_one_gap(config_dir, repo):
    policy = load(company(config_dir, 'version = 1\n[create]\nrequire = ["due"]\n'), None, repo)

    assert rules(evaluate(policy, card(sprint="Sprint 1"), "create")) == ["create.require.due"]


def test_a_complete_card_passes_the_company_policy(fake):
    assert evaluate(fake, complete_card(), "create") == []


def test_a_category_group_takes_at_most_one_value(fake):
    gaps = evaluate(fake, complete_card(labels=["planned", "intruder-ops", "SMALL"]), "create")

    assert rules(gaps) == ["categories.label.single"]
    assert "planned, intruder-ops" in gaps[0]["detail"]
    assert gaps[0]["fix"] == {"needs": "input"}


def test_at_most_one_value_holds_without_the_requirement_to_have_one(config_dir, repo):
    text = COMPANY.replace('"estimate", "categories"', '"estimate"')
    policy = load(company(config_dir, text), None, repo)

    assert rules(evaluate(policy, card(labels=["BIG", "SMALL"]), "create")) == [
        "categories.tag.single"
    ]
    assert evaluate(policy, card(labels=[]), "create") == []


def test_a_new_card_needs_one_value_of_each_required_group(fake):
    gaps = evaluate(fake, complete_card(labels=[]), "create")

    assert rules(gaps) == ["categories.label.required", "categories.tag.required"]
    assert gaps[0]["fix"] == {"needs": "input"}
    assert gaps[1]["fix"] == {"value": "SMALL"}


def test_a_skip_label_exempts_the_card_from_the_group(fake):
    skipped = complete_card(labels=["planned-team"], epic=None)

    assert evaluate(fake, skipped, "create") == []


def test_a_group_that_is_not_required_may_be_empty(config_dir, repo):
    project_layer(repo, "version = 1\n[categories.label]\nrequired = false\n")
    policy = load(company(config_dir), "alpha", repo)

    assert rules(evaluate(policy, complete_card(labels=["SMALL"]), "create")) == []


@pytest.mark.parametrize(
    ("minutes", "computed"),
    [(30, "SMALL"), (359, "SMALL"), (360, "SMALL"), (361, "BIG"), (600, "BIG")],
)
def test_the_derived_value_follows_the_estimate(fake, minutes, computed):
    wrong = "BIG" if computed == "SMALL" else "SMALL"
    right = complete_card(labels=["planned", computed], estimate_minutes=minutes)
    contradicts = complete_card(labels=["planned", wrong], estimate_minutes=minutes)

    assert evaluate(fake, right, "create") == []
    gaps = evaluate(fake, contradicts, "create")
    assert rules(gaps) == ["categories.tag.derive"]
    assert gaps[0]["fix"] == {"value": computed}
    assert gaps[0]["field"] == "labels"


def test_a_kept_value_is_never_replaced(fake):
    kept = complete_card(labels=["planned", "NEW"], estimate_minutes=600)

    assert evaluate(fake, kept, "create") == []


def test_a_derived_group_without_an_estimate_needs_input(fake):
    gaps = evaluate(fake, complete_card(labels=["planned"], estimate_minutes=None), "create")

    assert rules(gaps) == [
        "create.require.estimate",
        "categories.tag.required",
    ]
    assert gaps[1]["fix"] == {"needs": "input"}


def test_a_value_without_an_estimate_is_not_contradicted(config_dir, repo):
    text = COMPANY.replace('"estimate", "categories"', '"categories"')
    policy = load(company(config_dir, text), None, repo)

    assert evaluate(policy, complete_card(estimate_minutes=None), "create") == []


def test_a_skip_label_exempts_the_derived_check(fake):
    card_ = complete_card(labels=["planned-team", "BIG"], epic=None, estimate_minutes=30)

    assert evaluate(fake, card_, "create") == []


def test_epic_skip_label_means_no_epic(fake):
    with_epic = complete_card(labels=["planned-team"], epic="TS-1")
    gaps = evaluate(fake, with_epic, "create")

    assert rules(gaps) == ["epic.skip_when"]
    assert gaps[0]["field"] == "epic"
    assert gaps[0]["detail"] == "a card with this label must have no epic"
    assert rules(evaluate(fake, complete_card(epic=None), "create")) == ["create.require.epic"]
    assert evaluate(fake, complete_card(labels=["planned-team"], epic=None), "create") == []


def test_finish_stage_checks_only_the_finish_rules(fake):
    broken = card(title="no group", sections={}, start=None, spent_minutes=0)

    gaps = evaluate(fake, broken, "finish")

    assert rules(gaps) == ["finish.require.start", "finish.require.time_spent"]
    assert [g["field"] for g in gaps] == ["start", "time_spent"]
    assert evaluate(fake, card(start="2026-12-01", spent_minutes=60), "finish") == []
    assert rules(evaluate(fake, card(start="2026-12-01", spent_minutes=None), "finish")) == [
        "finish.require.time_spent"
    ]


def test_the_default_has_nothing_to_finish(repo):
    assert evaluate(default_policy(repo), card(), "finish") == []


def test_audit_applies_finish_rules_only_to_done_cards(fake):
    open_card = complete_card(status="in_progress")
    done = complete_card(status="done")

    assert evaluate(fake, open_card, "audit") == []
    assert rules(evaluate(fake, done, "audit")) == [
        "finish.require.start",
        "finish.require.time_spent",
    ]
    assert (
        evaluate(fake, complete_card(status="done", start="2026-12-01", spent_minutes=30), "audit")
        == []
    )


def test_audit_applies_the_create_rules(fake):
    gaps = evaluate(fake, card(title="plain", labels=[], sections={"Contexto": "x"}), "audit")

    assert rules(gaps) == [
        "title.format",
        "sections.required",
        "categories.label.required",
        "categories.tag.required",
    ]


def test_a_bug_without_a_caused_by_link_is_a_suggestion_in_the_audit(fake):
    bug = complete_card(type="bug", sections={"Problema": "p", "Pronto quando": "q"})

    gaps = evaluate(fake, bug, "audit")

    assert rules(gaps) == ["links.bug.caused_by"]
    assert gaps[0]["severity"] == "suggestion"
    assert gaps[0]["fix"] == {"needs": "input"}
    linked = {**bug, "links": [{"kind": "caused_by", "ref": "TS-9"}]}
    assert evaluate(fake, linked, "audit") == []
    assert (
        evaluate(fake, {**bug, "type": "task", "sections": complete_card()["sections"]}, "audit")
        == []
    )
    assert evaluate(fake, bug, "create") == []


def test_the_caused_by_suggestion_is_off_by_default(repo):
    bug = card(
        type="bug",
        sections={"Contexto": "c", "Pronto quando": "p", "Como reproduzir": "r", "Evidência": "e"},
    )

    assert evaluate(default_policy(repo), bug, "audit") == []


def test_every_other_gap_is_required(fake):
    gaps = evaluate(fake, card(title="plain", labels=[], sections={}, epic=None), "audit")

    assert gaps
    assert {g["severity"] for g in gaps} == {"required"}
    assert all(set(g) == {"rule", "field", "detail", "fix", "severity"} for g in gaps)


def test_edit_applies_only_the_rules_of_the_changed_fields(fake):
    broken = card(title="plain", labels=[], sections={}, epic=None, estimate_minutes=None)

    assert evaluate(fake, broken, "edit") == []
    assert rules(evaluate(fake, {**broken, "changed": {"title"}}, "edit")) == ["title.format"]
    assert rules(evaluate(fake, {**broken, "changed": {"description"}}, "edit")) == [
        "sections.required",
        "sections.required",
    ]
    assert rules(evaluate(fake, {**broken, "changed": {"epic"}}, "edit")) == ["create.require.epic"]
    assert rules(evaluate(fake, {**broken, "changed": {"estimate"}}, "edit")) == [
        "create.require.estimate"
    ]


def test_edit_checks_categories_when_the_labels_change(fake):
    two = complete_card(labels=["planned", "intruder-ops", "SMALL"], estimate_minutes=30)
    wrong = complete_card(labels=["planned", "BIG"], estimate_minutes=30)

    assert rules(evaluate(fake, {**two, "changed": {"add_labels"}}, "edit")) == [
        "categories.label.single"
    ]
    assert evaluate(fake, {**two, "changed": {"title"}}, "edit") == []
    for field in ("labels", "remove_labels", "estimate_minutes", "estimate"):
        gaps = evaluate(fake, {**wrong, "changed": {field}}, "edit")
        assert rules(gaps) == ["categories.tag.derive"], field
    assert evaluate(fake, {**wrong, "changed": {"due"}}, "edit") == []


def test_edit_does_not_demand_a_missing_category(fake):
    bare = complete_card(labels=[])

    assert evaluate(fake, {**bare, "changed": {"labels", "estimate"}}, "edit") == []


def test_edit_checks_the_sprint_rule_when_the_sprint_or_the_due_changes(repo):
    policy = default_policy(repo)
    sprint = card(sprint="Sprint 1")

    assert evaluate(policy, sprint, "edit") == []
    assert rules(evaluate(policy, {**sprint, "changed": {"sprint"}}, "edit")) == [
        "create.due_with_sprint"
    ]


def test_edit_title_follows_the_epic_prefix(repo):
    policy = default_policy(repo)
    changed = card(title="text", epic_prefix="FRONT", changed={"title"})

    assert rules(evaluate(policy, changed, "edit")) == ["title.format"]
