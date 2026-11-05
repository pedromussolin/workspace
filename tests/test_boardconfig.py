import copy
import tomllib
from pathlib import Path

import pytest

from ws.boardconfig import BoardMissing, load_board, parse_board
from ws.taskmodel import Status
from ws.userconfig import ConfigInvalid

EXAMPLE = """\
[board]
remote = "origin"
lookback_days = 120
fetch = true
ignore_repos = ["*-workspace"]
direct_deploy_repos = ["*-argocd"]

[[board.environments]]
name = "sandbox"
branches = ["sandbox", "staging"]
status = "validation"

[[board.environments]]
name = "master"
branches = ["master", "main"]
status = "ready_deploy"

[[board.environments]]
name = "production"
status = "done"
deploy_repo = "{repo}-argocd"
deploy_branch = "master"
image_tag = 'prod-([0-9a-f]{7,40})'

[board.repos."some-repo"]
deploy_repo = "some-deploy-repo"

[board.repos."some-repo".branches]
sandbox = ["homolog"]

[board.statuses]
in_progress = "Em andamento"
validation = "In Validation"
ready_deploy = "Ready Deploy"
done = "Concluído"
"""

VALID = tomllib.loads(EXAMPLE)["board"]
PATH = Path("config.toml")


def parse(table):
    return parse_board(table, PATH)


def test_valid_example_parses():
    cfg = parse(VALID)
    sandbox, master, production = cfg.environments

    assert [env.name for env in cfg.environments] == ["sandbox", "master", "production"]
    assert (cfg.remote, cfg.lookback_days, cfg.fetch) == ("origin", 120, True)
    assert [env.rung for env in cfg.environments] == [2, 3, 4]
    assert production.deploy_repo == "{repo}-argocd"
    assert production.deploy_branch == "master"
    assert production.image_tag.pattern == "prod-([0-9a-f]{7,40})"
    assert production.branches == ()
    assert sandbox.deploy_repo is None and sandbox.image_tag is None
    assert cfg.statuses[Status.DONE] == "Concluído"
    assert cfg.branches_for("some-repo", sandbox) == ("homolog",)
    assert cfg.branches_for("other", sandbox) == ("sandbox", "staging")
    assert cfg.branches_for("some-repo", master) == ("master", "main")
    assert cfg.deploy_repo_for("some-repo", production) == "some-deploy-repo"
    assert cfg.deploy_repo_for("demo-api", production) == "demo-api-argocd"
    assert cfg.ignored("artemis-workspace") and not cfg.ignored("demo-api")
    assert cfg.direct_deploy("demo-api-argocd") and not cfg.direct_deploy("demo-api")


def test_defaults_when_keys_absent():
    table = {k: copy.deepcopy(VALID[k]) for k in ("environments", "statuses")}

    cfg = parse(table)

    assert cfg.remote == "origin"
    assert cfg.lookback_days == 120
    assert cfg.fetch is True
    assert cfg.environments[2].deploy_branch == "master"
    assert cfg.ignore_repos == ()
    assert cfg.direct_deploy_repos == ()
    assert cfg.repo_branches == {}
    assert cfg.repo_deploy == {}


def mutated(change):
    table = copy.deepcopy(VALID)
    change(table)
    return table


def _duplicate_name(t):
    t["environments"][1]["name"] = "sandbox"


def _status_todo(t):
    t["environments"][0]["status"] = "todo"


def _not_rising(t):
    t["environments"][0]["status"] = "ready_deploy"
    t["environments"][1]["status"] = "validation"


def _both(t):
    t["environments"][0]["deploy_repo"] = "{repo}-argocd"


def _neither(t):
    del t["environments"][0]["branches"]


def _no_group(t):
    t["environments"][2]["image_tag"] = "prod-[0-9a-f]+"


def _bad_regex(t):
    t["environments"][2]["image_tag"] = "prod-("


def _unknown_env(t):
    t["repos"]["some-repo"]["branches"]["nowhere"] = ["x"]


def _no_in_progress(t):
    del t["statuses"]["in_progress"]


def _no_status_name(t):
    del t["statuses"]["done"]


def _zero_lookback(t):
    t["lookback_days"] = 0


def _fetch_string(t):
    t["fetch"] = "yes"


def _ignore_not_list(t):
    t["ignore_repos"] = "x"


def _bad_repo_deploy(t):
    t["repos"]["some-repo"]["deploy_repo"] = ""


@pytest.mark.parametrize(
    ("change", "key_path"),
    [
        (_duplicate_name, "board.environments[1].name"),
        (_status_todo, "board.environments[0].status"),
        (_not_rising, "board.environments[1].status"),
        (_both, "board.environments[0]"),
        (_neither, "board.environments[0]"),
        (_no_group, "board.environments[2].image_tag"),
        (_bad_regex, "board.environments[2].image_tag"),
        (_unknown_env, "board.repos.some-repo.branches.nowhere"),
        (_no_in_progress, "board.statuses.in_progress"),
        (_no_status_name, "board.statuses.done"),
        (_zero_lookback, "board.lookback_days"),
        (_fetch_string, "board.fetch"),
        (_ignore_not_list, "board.ignore_repos"),
        (_bad_repo_deploy, "board.repos.some-repo.deploy_repo"),
    ],
)
def test_invalid_raises_config_invalid(change, key_path):
    with pytest.raises(ConfigInvalid) as error:
        parse(mutated(change))

    assert str(error.value).startswith(f"{PATH}: ")
    assert key_path in str(error.value)


def test_load_board_reads_the_table(tmp_path, monkeypatch):
    (tmp_path / "config.toml").write_text(EXAMPLE, encoding="utf-8")
    monkeypatch.setenv("WS_CONFIG_DIR", str(tmp_path))

    assert load_board().remote == "origin"


def test_load_board_without_table_raises_board_missing(tmp_path, monkeypatch):
    (tmp_path / "config.toml").write_text('[jira]\nsite = "x"\n', encoding="utf-8")
    monkeypatch.setenv("WS_CONFIG_DIR", str(tmp_path))

    with pytest.raises(BoardMissing):
        load_board()
