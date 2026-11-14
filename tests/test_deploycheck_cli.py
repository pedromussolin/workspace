import json
import time
from pathlib import Path

import pytest
from test_deploycheck import config_text, make_argocd

from ws.cli import main


@pytest.fixture
def configured(tmp_path: Path, monkeypatch) -> Path:
    argocd = make_argocd(tmp_path)
    cfg = tmp_path / "cfg"
    cfg.mkdir()
    monkeypatch.setenv("WS_CONFIG_DIR", str(cfg))
    (cfg / "config.toml").write_text(config_text(argocd))
    return cfg


def test_deploy_check_has_help():
    with pytest.raises(SystemExit) as exc:
        main(["deploy-check", "--help"])
    assert exc.value.code == 0


def test_plan_prints_json_in_order(configured, capsys):
    assert main(["deploy-check", "plan", "--env", "sandbox"]) == 0
    plan = json.loads(capsys.readouterr().out)
    assert [item["key"] for item in plan["services"]] == ["shared", "bff"]
    assert plan["services"][0]["deploy"]["time"] == "2026-11-03T12:00:00Z"


def test_plan_with_at_and_only(configured, capsys):
    argv = [
        "deploy-check",
        "plan",
        "--env",
        "prod",
        "--at",
        "2026-11-03T14:00:00Z",
        "--only",
        "bff",
    ]
    assert main(argv) == 0
    plan = json.loads(capsys.readouterr().out)
    assert [item["key"] for item in plan["services"]] == ["bff"]
    assert plan["services"][0]["deploy"]["source"] == "at"
    assert plan["services"][0]["deploy"]["time"] == "2026-11-03T14:00:00Z"


def test_script_prints_plain_javascript(configured, capsys):
    argv = ["deploy-check", "script", "bff", "--env", "sandbox", "--at", "2026-11-03T12:00:00Z"]
    assert main(argv) == 0
    out = capsys.readouterr().out
    assert out.startswith("// Deploy check program")
    assert '"service": "svc-bff"' in out
    assert "/*ws:params*/" not in out


def test_queries_prints_json(configured, capsys):
    argv = ["deploy-check", "queries", "bff", "--env", "sandbox", "--at", "2026-11-03T12:00:00Z"]
    assert main(argv) == 0
    queries = json.loads(capsys.readouterr().out)
    assert queries[0]["tool"] == "aggregate_spans"
    assert len(queries) == 15


def test_config_missing_exits_2(tmp_path, monkeypatch, capsys):
    monkeypatch.setenv("WS_CONFIG_DIR", str(tmp_path / "no-config"))
    assert main(["deploy-check", "plan", "--env", "sandbox"]) == 2
    assert "config.toml" in capsys.readouterr().err


def test_config_without_the_table_exits_2(tmp_path, monkeypatch, capsys):
    (tmp_path / "config.toml").write_text("[jira]\nsite = 'x'\n")
    monkeypatch.setenv("WS_CONFIG_DIR", str(tmp_path))
    assert main(["deploy-check", "plan", "--env", "sandbox"]) == 2
    assert "deploy_check.order" in capsys.readouterr().err


def test_unknown_env_service_or_bad_at(configured, capsys):
    assert main(["deploy-check", "plan", "--env", "nowhere"]) == 1
    assert "unknown env" in capsys.readouterr().err
    assert main(["deploy-check", "script", "ghost", "--env", "sandbox", "--at", "2026-11-03"]) == 1
    assert "ghost" in capsys.readouterr().err
    with pytest.raises(SystemExit) as exc:
        main(["deploy-check", "plan", "--env", "sandbox", "--at", "yesterday"])
    assert exc.value.code == 2


@pytest.fixture
def local_tz(monkeypatch):
    def use(name: str) -> None:
        monkeypatch.setenv("TZ", name)
        time.tzset()

    yield use
    monkeypatch.undo()
    time.tzset()


def test_naive_at_is_local_time_converted_to_utc(configured, capsys, local_tz):
    local_tz("BRT3")  # UTC-3, no tz database needed
    assert main(["deploy-check", "plan", "--env", "prod", "--at", "2026-11-03T09:00:00"]) == 0
    deploy = json.loads(capsys.readouterr().out)["services"][0]["deploy"]
    assert deploy["time"] == "2026-11-03T12:00:00Z"


def test_at_with_an_offset_or_z_ignores_the_local_zone(configured, capsys, local_tz):
    local_tz("BRT3")
    for text in ("2026-11-03T12:00:00Z", "2026-11-03T14:00:00+02:00"):
        assert main(["deploy-check", "plan", "--env", "prod", "--at", text]) == 0
        deploy = json.loads(capsys.readouterr().out)["services"][0]["deploy"]
        assert deploy["time"] == "2026-11-03T12:00:00Z"


def test_help_says_naive_at_is_local_time(capsys):
    with pytest.raises(SystemExit):
        main(["deploy-check", "plan", "--help"])
    assert "local time" in " ".join(capsys.readouterr().out.split())
