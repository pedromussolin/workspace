import copy
import tomllib
from pathlib import Path

import pytest

from ws.boardconfig import (
    BoardMissing,
    BranchProof,
    CommandProof,
    FileProof,
    TagProof,
    load_board,
    parse_board,
)
from ws.taskmodel import Status
from ws.userconfig import ConfigInvalid

EXAMPLE = """\
[board]
remote = "origin"
lookback_days = 120
fetch = true
default_profile = "gitops"

[[board.profiles.gitops.environments]]
name = "sandbox"
status = "validation"
proof = "branch"
branches = ["sandbox", "staging"]

[[board.profiles.gitops.environments]]
name = "master"
status = "ready_deploy"
proof = "branch"
branches = ["master", "main"]

[[board.profiles.gitops.environments]]
name = "production"
status = "done"
proof = "file"
deploy_repo = "{repo}-argocd"
deploy_branch = "master"
image_tag = 'prod-([0-9a-f]{7,40})'

[[board.profiles.release-tag.environments]]
name = "main"
status = "ready_deploy"
proof = "branch"
branches = ["main"]

[[board.profiles.release-tag.environments]]
name = "production"
status = "done"
proof = "tag"
tag = "v*"

[[board.profiles.api.environments]]
name = "production"
status = "done"
proof = "command"
command = ["~/bin/deployed-sha", "{repo}", "{env}"]
timeout = 20

[board.repos."some-repo"]
profile = "release-tag"

[board.repos."data-*"]
inactive = ["sandbox"]

[board.repos."*-argocd"]
ignore = true

[board.repos."*-workspace"]
ignore = true

[board.statuses]
in_progress = "Em andamento"
validation = "In Validation"
ready_deploy = "Ready Deploy"
done = "Concluído"
"""

VALID = tomllib.loads(EXAMPLE)["board"]
PATH = Path("config.toml")
FIRST_VERSION = 'is from the first version; use [board.profiles.<name>] and [board.repos."<glob>"]'


def parse(table):
    return parse_board(table, PATH)


def names(environments):
    return tuple(env.name for env in environments)


def test_spec_example_parses():
    cfg = parse(VALID)

    assert (cfg.remote, cfg.lookback_days, cfg.fetch) == ("origin", 120, True)
    assert cfg.default_profile == "gitops"
    assert list(cfg.profiles) == ["gitops", "release-tag", "api"]
    sandbox, master, production = cfg.profiles["gitops"].environments
    assert [env.rung for env in cfg.profiles["gitops"].environments] == [2, 3, 4]
    assert sandbox.proof == BranchProof(("sandbox", "staging"))
    assert master.proof == BranchProof(("master", "main"))
    assert isinstance(production.proof, FileProof)
    assert production.proof.deploy_repo == "{repo}-argocd"
    assert production.proof.deploy_branch == "master"
    assert production.proof.image_tag.pattern == "prod-([0-9a-f]{7,40})"
    assert cfg.profiles["release-tag"].environments[1].proof == TagProof("v*")
    assert cfg.profiles["api"].environments[0].proof == CommandProof(
        ("~/bin/deployed-sha", "{repo}", "{env}"), 20
    )
    assert cfg.statuses[Status.DONE] == "Concluído"
    assert cfg.settings_for("data-api").inactive == ("sandbox",)
    assert cfg.ignored("x-argocd") and cfg.ignored("demo-workspace")
    assert not cfg.ignored("demo-api") and not cfg.ignored("data-api")
    assert names(cfg.environments_for("data-api")) == ("master", "production")
    assert names(cfg.profile_for("data-api").environments) == ("sandbox", "master", "production")
    assert cfg.profile_for("some-repo").name == "release-tag"
    assert names(cfg.environments_for("demo-api")) == ("sandbox", "master", "production")
    assert names(cfg.environments_for("some-repo")) == ("main", "production")
    assert cfg.settings_for("demo-api") is None
    assert cfg.uses_tags("some-repo") and not cfg.uses_tags("demo-api")


def test_exact_key_beats_glob_and_first_glob_wins():
    table = copy.deepcopy(VALID)
    table["repos"] = {
        "demo-*": {"inactive": ["sandbox"]},
        "*-api": {"profile": "release-tag"},
        "demo-api": {"profile": "api"},
    }

    cfg = parse(table)

    assert cfg.settings_for("demo-api").key == "demo-api"
    assert cfg.settings_for("demo-web-api").key == "demo-*"
    assert cfg.settings_for("other-api").key == "*-api"
    assert cfg.settings_for("other") is None
    assert names(cfg.environments_for("demo-api")) == ("production",)


def test_defaults_when_keys_absent():
    table = {k: copy.deepcopy(VALID[k]) for k in ("default_profile", "profiles", "statuses")}
    del table["profiles"]["gitops"]["environments"][2]["deploy_branch"]
    del table["profiles"]["api"]["environments"][0]["timeout"]

    cfg = parse(table)

    assert (cfg.remote, cfg.lookback_days, cfg.fetch) == ("origin", 120, True)
    assert cfg.repos == ()
    assert cfg.profiles["gitops"].environments[2].proof.deploy_branch == "master"
    assert cfg.profiles["api"].environments[0].proof.timeout == 20


G = ("profiles", "gitops", "environments")
T = ("profiles", "release-tag", "environments", 1)
A = ("profiles", "api", "environments", 0)
GITOPS = "board.profiles.gitops.environments"
TAG = "board.profiles.release-tag.environments[1]"
API = "board.profiles.api.environments[0]"


def _target(table, keys):
    for key in keys:
        table = table[key]
    return table


def put(*keys_and_value):
    *keys, last, value = keys_and_value
    return lambda table: _target(table, keys).__setitem__(last, value)


def drop(*keys):
    *keys, last = keys
    return lambda table: _target(table, keys).pop(last)


@pytest.mark.parametrize(
    ("change", "key_path"),
    [
        (put("remote", ""), "board.remote"),
        (put("lookback_days", 0), "board.lookback_days"),
        (put("fetch", "yes"), "board.fetch"),
        (put("colour", "x"), "board.colour"),
        (drop("default_profile"), "board.default_profile"),
        (put("default_profile", "nope"), "board.default_profile"),
        (put("default_profile", ["gitops"]), "board.default_profile"),
        (drop("profiles"), "board.profiles"),
        (put("profiles", {}), "board.profiles"),
        (put("profiles", "gitops", []), "board.profiles.gitops"),
        (put("profiles", "gitops", "colour", 1), "board.profiles.gitops.colour"),
        (put(*G[:2], "environments", []), GITOPS),
        (put(*G, 0, "x"), f"{GITOPS}[0]"),
        (drop(*G, 0, "name"), f"{GITOPS}[0].name"),
        (put(*G, 1, "name", "sandbox"), f"{GITOPS}[1].name"),
        (put(*G, 0, "status", "todo"), f"{GITOPS}[0].status"),
        (put(*G, 1, "status", "validation"), f"{GITOPS}[1].status"),
        (drop(*G, 0, "proof"), f"{GITOPS}[0].proof"),
        (put(*G, 0, "proof", "deploy"), f"{GITOPS}[0].proof"),
        (put(*G, 0, "proof", ["branch"]), f"{GITOPS}[0].proof"),
        (put(*G, 0, "colour", 1), f"{GITOPS}[0].colour"),
        (put(*G, 0, "tag", "v*"), f"{GITOPS}[0].tag"),
        (drop(*G, 0, "branches"), f"{GITOPS}[0].branches"),
        (put(*G, 0, "branches", []), f"{GITOPS}[0].branches"),
        (put(*G, 0, "branches", ["a", 1]), f"{GITOPS}[0].branches"),
        (put(*G, 2, "branches", ["x"]), f"{GITOPS}[2].branches"),
        (drop(*G, 2, "deploy_repo"), f"{GITOPS}[2].deploy_repo"),
        (put(*G, 2, "deploy_repo", "{name}-x"), f"{GITOPS}[2].deploy_repo"),
        (put(*G, 2, "deploy_repo", "{repo-x"), f"{GITOPS}[2].deploy_repo"),
        (put(*G, 2, "deploy_repo", "{repo!r}"), f"{GITOPS}[2].deploy_repo"),
        (put(*G, 2, "deploy_branch", 1), f"{GITOPS}[2].deploy_branch"),
        (drop(*G, 2, "image_tag"), f"{GITOPS}[2].image_tag"),
        (put(*G, 2, "image_tag", "prod-[0-9]+"), f"{GITOPS}[2].image_tag"),
        (put(*G, 2, "image_tag", "prod-("), f"{GITOPS}[2].image_tag"),
        (drop(*T, "tag"), f"{TAG}.tag"),
        (put(*T, "tag", ""), f"{TAG}.tag"),
        (put(*T, "timeout", 5), f"{TAG}.timeout"),
        (drop(*A, "command"), f"{API}.command"),
        (put(*A, "command", []), f"{API}.command"),
        (put(*A, "command", "x"), f"{API}.command"),
        (put(*A, "command", ["x", 1]), f"{API}.command"),
        (put(*A, "command", ["x", "{sha}"]), f"{API}.command"),
        (put(*A, "timeout", 0), f"{API}.timeout"),
        (put(*A, "timeout", True), f"{API}.timeout"),
        (put("repos", []), "board.repos"),
        (put("repos", "x", 1), 'board.repos."x"'),
        (put("repos", "some-repo", "profile", "nope"), 'board.repos."some-repo".profile'),
        (put("repos", "some-repo", "profile", ["api"]), 'board.repos."some-repo".profile'),
        (put("repos", "data-*", "inactive", ["nope"]), 'board.repos."data-*".inactive'),
        (put("repos", "data-*", "inactive", "sandbox"), 'board.repos."data-*".inactive'),
        (put("repos", "some-repo", "inactive", ["sandbox"]), 'board.repos."some-repo".inactive'),
        (put("repos", "*-argocd", "ignore", "yes"), 'board.repos."*-argocd".ignore'),
        (put("repos", "*-argocd", "profile", "gitops"), 'board.repos."*-argocd"'),
        (put("repos", "some-repo", "colour", 1), 'board.repos."some-repo".colour'),
        (put("statuses", []), "board.statuses"),
        (drop("statuses", "in_progress"), "board.statuses.in_progress"),
        (drop("statuses", "done"), "board.statuses.done"),
        (put("statuses", "done", ""), "board.statuses.done"),
        (put("statuses", "todo", "A fazer"), "board.statuses.todo"),
    ],
)
def test_invalid_raises_config_invalid(change, key_path):
    table = copy.deepcopy(VALID)
    change(table)

    with pytest.raises(ConfigInvalid) as error:
        parse(table)

    assert str(error.value).startswith(f"{PATH}: {key_path} ")


@pytest.mark.parametrize(
    ("change", "key_path"),
    [
        (put("environments", []), "board.environments"),
        (put("ignore_repos", ["x"]), "board.ignore_repos"),
        (put("direct_deploy_repos", ["x"]), "board.direct_deploy_repos"),
        (
            put("repos", "some-repo", "branches", {"sandbox": ["x"]}),
            'board.repos."some-repo".branches',
        ),
        (put("repos", "some-repo", "deploy_repo", "x"), 'board.repos."some-repo".deploy_repo'),
    ],
)
def test_first_version_keys_show_the_new_form(change, key_path):
    table = copy.deepcopy(VALID)
    change(table)

    with pytest.raises(ConfigInvalid) as error:
        parse(table)

    assert str(error.value) == f"{PATH}: {key_path} {FIRST_VERSION}"


def test_load_board_reads_the_table(tmp_path, monkeypatch):
    (tmp_path / "config.toml").write_text(EXAMPLE, encoding="utf-8")
    monkeypatch.setenv("WS_CONFIG_DIR", str(tmp_path))

    assert load_board().default_profile == "gitops"


def test_load_board_without_table_raises_board_missing(tmp_path, monkeypatch):
    (tmp_path / "config.toml").write_text('[jira]\nsite = "x"\n', encoding="utf-8")
    monkeypatch.setenv("WS_CONFIG_DIR", str(tmp_path))

    with pytest.raises(BoardMissing):
        load_board()


def with_repos(repos):
    table = copy.deepcopy(VALID)
    table["repos"] = repos
    return table


def test_repo_base_defaults_to_master():
    assert parse(copy.deepcopy(VALID)).base_for("acme-api") == "master"
    assert parse(with_repos({"acme-api": {"base": "main"}})).base_for("acme-api") == "main"
    cfg = parse(with_repos({"acme-*": {"base": "develop"}}))
    assert cfg.base_for("acme-front") == "develop"
    assert cfg.base_for("other") == "master"


@pytest.mark.parametrize("base", ["", "-x", "a..b", 1])
def test_repo_base_must_be_a_branch_name(base):
    with pytest.raises(ConfigInvalid) as error:
        parse(with_repos({"acme-api": {"base": base}}))

    assert str(error.value).startswith(f'{PATH}: board.repos."acme-api".base ')


def test_repo_base_refuses_ignore_with_base():
    with pytest.raises(ConfigInvalid) as error:
        parse(with_repos({"acme-api": {"ignore": True, "base": "main"}}))

    assert "must hold ignore = true alone" in str(error.value)


def test_prefix_repos_maps_a_title_prefix():
    table = copy.deepcopy(VALID)
    assert parse(table).prefix_repos == {}
    table["prefix_repos"] = {"BACK": ["acme-api"]}
    assert parse(table).prefix_repos == {"BACK": ("acme-api",)}


@pytest.mark.parametrize(
    ("key", "value"),
    [("BACK", "acme-api"), ("BACK", []), ("BACK", ["../x"]), ("[X]", ["acme-api"])],
)
def test_prefix_repos_refuses_bad_entries(key, value):
    table = copy.deepcopy(VALID)
    table["prefix_repos"] = {key: value}

    with pytest.raises(ConfigInvalid) as error:
        parse(table)

    assert f"board.prefix_repos.{key} " in str(error.value)


def test_review_categories_for_a_repo():
    cfg = parse(with_repos({"acme-front": {"review_categories": {"front": ["src/app/models/**"]}}}))

    assert cfg.review_categories_for("acme-front") == {"front": ("src/app/models/**",)}
    assert cfg.review_categories_for("acme-api") == {}
    glob = parse(with_repos({"acme-*": {"review_categories": {"front": ["x/**"]}}}))
    assert glob.review_categories_for("acme-front") == {"front": ("x/**",)}


@pytest.mark.parametrize(
    ("value", "where"),
    [
        ({"nope": ["x"]}, "review_categories"),
        ({"front": "x"}, "review_categories.front"),
        ({"front": []}, "review_categories.front"),
        ({"front": [""]}, "review_categories.front"),
        (1, "review_categories"),
    ],
)
def test_review_categories_refuses_bad_entries(value, where):
    with pytest.raises(ConfigInvalid) as error:
        parse(with_repos({"acme-front": {"review_categories": value}}))

    assert str(error.value).startswith(f'{PATH}: board.repos."acme-front".{where}')
