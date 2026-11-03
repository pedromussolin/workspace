import subprocess
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

from ws import deploycheck
from ws.userconfig import ConfigInvalid, ConfigMissing

GIT = ["git", "-c", "user.name=Test", "-c", "user.email=test@example.invalid"]
T = datetime(2026, 11, 3, 12, 0, tzinfo=UTC)

VALUES = """\
image:
  repository: registry.example/app
  tag: "{tag}"
env:
  - name: DD_ENV
    value: "env-x"
  - name: DD_VERSION
    value: "{version}"
"""


def git(cwd: Path, *args: str, env_time: datetime | None = None) -> str:
    env = None
    if env_time is not None:
        iso = env_time.isoformat()
        env = {"GIT_COMMITTER_DATE": iso, "GIT_AUTHOR_DATE": iso, "PATH": "/usr/bin:/bin"}
    result = subprocess.run(
        [*GIT, *args], cwd=cwd, check=True, capture_output=True, text=True, env=env
    )
    return result.stdout.strip()


def make_argocd(root: Path, *, tag="abc1234", version="abc1234", when=T) -> Path:
    repo = root / "argocd"
    repo.mkdir()
    git(repo, "init", "-q", "-b", "master")
    (repo / "envs").mkdir()
    (repo / "envs" / "other.yaml").write_text("x: 1\n")
    git(repo, "add", ".")
    git(repo, "commit", "-q", "-m", "inicial", env_time=when - timedelta(days=3))
    (repo / "envs" / "svc-x.yaml").write_text(VALUES.format(tag="old0000", version="old0000"))
    git(repo, "add", ".")
    git(
        repo,
        "commit",
        "-q",
        "-m",
        "Update image tag in values.yaml",
        env_time=when - timedelta(days=1),
    )
    (repo / "envs" / "svc-x.yaml").write_text(VALUES.format(tag=tag, version=version))
    git(repo, "add", ".")
    git(repo, "commit", "-q", "-m", "Update image tag in values.yaml", env_time=when)
    (repo / "envs" / "other.yaml").write_text("x: 2\n")
    git(repo, "add", ".")
    git(repo, "commit", "-q", "-m", "mexe em outro arquivo", env_time=when + timedelta(hours=1))
    return repo


def config_text(argocd: Path, *, order='["shared", "bff"]', extra_service="") -> str:
    return f"""
[deploy_check]
order = {order}
min_requests = 50

[deploy_check.env_tags]
sandbox = "env-sbx"
prod = "env-prod"

[deploy_check.services.shared]
service = "svc-shared"
kind = "apm"
argocd = "{argocd}"
values = {{ sandbox = "envs/svc-x.yaml", prod = "envs/svc-x.yaml" }}

[deploy_check.services.bff]
service = "svc-bff"
kind = "apm"
span_filter = "operation_name:web.request"
argocd = "{argocd}"
values = {{ sandbox = "envs/svc-x.yaml", prod = "envs/svc-x.yaml" }}
{extra_service}
"""


@pytest.fixture
def argocd(tmp_path: Path) -> Path:
    return make_argocd(tmp_path)


@pytest.fixture
def settings(tmp_path: Path, argocd: Path, monkeypatch) -> deploycheck.DeployCheckSettings:
    monkeypatch.setenv("WS_CONFIG_DIR", str(tmp_path / "cfg"))
    (tmp_path / "cfg").mkdir()
    (tmp_path / "cfg" / "config.toml").write_text(config_text(argocd))
    return deploycheck.load_settings()


def test_settings_require_order_services_env_tags(tmp_path, argocd, monkeypatch):
    cfg = tmp_path / "cfg"
    cfg.mkdir()
    monkeypatch.setenv("WS_CONFIG_DIR", str(cfg))
    with pytest.raises(ConfigMissing):
        deploycheck.load_settings()
    path = cfg / "config.toml"
    path.write_text("[jira]\nsite = 'x'\n")
    with pytest.raises(ConfigInvalid, match="deploy_check.order"):
        deploycheck.load_settings()
    ok = config_text(argocd)
    path.write_text(ok.replace('order = ["shared", "bff"]', 'order = ["shared", "ghost"]'))
    with pytest.raises(ConfigInvalid, match="ghost"):
        deploycheck.load_settings()
    path.write_text(ok.replace("[deploy_check.env_tags]", "[deploy_check.no_tags]"))
    with pytest.raises(ConfigInvalid, match="env_tags"):
        deploycheck.load_settings()
    path.write_text(ok.replace('kind = "apm"', 'kind = "weird"', 1))
    with pytest.raises(ConfigInvalid, match="kind"):
        deploycheck.load_settings()
    path.write_text(ok)
    loaded = deploycheck.load_settings()
    assert loaded.order == ("shared", "bff")
    assert (loaded.window_minutes, loaded.settle_minutes) == (30, 5)
    assert (loaded.baseline_hours, loaded.min_requests) == (24, 50)
    assert loaded.env_tags == {"sandbox": "env-sbx", "prod": "env-prod"}
    assert loaded.services["bff"].span_filter == "operation_name:web.request"
    assert loaded.services["shared"].span_filter is None


def test_deploy_of_last_tag_commit_tag_and_dd_version(argocd):
    found = deploycheck.deploy_of(argocd, "envs/svc-x.yaml")
    assert found["time"] == "2026-11-03T12:00:00Z"
    assert found["subject"] == "Update image tag in values.yaml"
    assert found["tag"] == "abc1234"
    assert found["dd_version"] == "abc1234"
    assert found["sha"] == git(argocd, "log", "-1", "--format=%H", "--", "envs/svc-x.yaml")
    assert found["behind"] == 0


def test_deploy_of_reads_a_mapping_style_dd_version(tmp_path):
    repo = make_argocd(tmp_path)
    (repo / "envs" / "svc-x.yaml").write_text("image:\n  tag: v9\nextraEnv:\n  DD_VERSION: v9-dd\n")
    found = deploycheck.deploy_of(repo, "envs/svc-x.yaml")
    assert (found["tag"], found["dd_version"]) == ("v9", "v9-dd")


def test_deploy_of_warns_when_behind_upstream(tmp_path, argocd):
    remote = tmp_path / "remote.git"
    subprocess.run(["git", "init", "-q", "--bare", "-b", "master", str(remote)], check=True)
    git(argocd, "remote", "add", "origin", str(remote))
    git(argocd, "push", "-q", "-u", "origin", "master")
    other = tmp_path / "other"
    subprocess.run(["git", "clone", "-q", str(remote), str(other)], check=True)
    (other / "extra.txt").write_text("x\n")
    git(other, "add", ".")
    git(other, "commit", "-q", "-m", "novo")
    git(other, "push", "-q")
    git(argocd, "fetch", "-q")
    assert deploycheck.deploy_of(argocd, "envs/svc-x.yaml")["behind"] == 1


def test_deploy_of_unknown_values_file_is_an_error(argocd):
    with pytest.raises(deploycheck.DeployCheckError, match="no commit"):
        deploycheck.deploy_of(argocd, "envs/ghost.yaml")


def test_plan_in_order_with_at_override(settings):
    now = T + timedelta(hours=1)
    plan = deploycheck.plan(settings, "sandbox", at=None, only=None, now=now)
    assert [item["key"] for item in plan["services"]] == ["shared", "bff"]
    first = plan["services"][0]
    assert first["service"] == "svc-shared"
    assert first["env_tag"] == "env-sbx"
    assert first["deploy"]["source"] == "argocd"
    assert first["deploy"]["time"] == "2026-11-03T12:00:00Z"
    assert first["complete"] is True

    at = datetime(2026, 11, 3, 14, 0, tzinfo=UTC)
    moved = deploycheck.plan(settings, "prod", at=at, only=None, now=at + timedelta(minutes=10))
    one = moved["services"][1]
    assert one["deploy"]["source"] == "at"
    assert one["deploy"]["time"] == "2026-11-03T14:00:00Z"
    assert one["deploy"]["dd_version"] == "abc1234"
    assert one["complete"] is False
    assert one["ready_at"] == "2026-11-03T14:35:00Z"


def test_plan_warns_when_behind_and_rejects_unknown_env(settings, monkeypatch):
    real = deploycheck.deploy_of

    def behind(argocd, values):
        return {**real(argocd, values), "behind": 2}

    monkeypatch.setattr(deploycheck, "deploy_of", behind)
    plan = deploycheck.plan(settings, "sandbox", at=None, only=["bff"], now=T + timedelta(hours=1))
    assert plan["warnings"] and "behind" in plan["warnings"][0] and "bff" in plan["warnings"][0]
    with pytest.raises(deploycheck.DeployCheckError, match="env"):
        deploycheck.plan(settings, "nowhere", at=None, only=None, now=T)


def test_plan_only_filters(settings):
    now = T + timedelta(hours=1)
    plan = deploycheck.plan(settings, "sandbox", at=None, only=["bff"], now=now)
    assert [item["key"] for item in plan["services"]] == ["bff"]
    with pytest.raises(deploycheck.DeployCheckError, match="ghost"):
        deploycheck.plan(settings, "sandbox", at=None, only=["ghost"], now=now)


def test_windows_30_before_30_after_from_5_minutes(settings):
    found = deploycheck.windows(T, settings, now=T + timedelta(hours=2))
    assert found["before"]["from"] == "2026-11-03T11:30:00Z"
    assert found["before"]["to"] == "2026-11-03T12:00:00Z"
    assert found["after"]["from"] == "2026-11-03T12:05:00Z"
    assert found["after"]["to"] == "2026-11-03T12:35:00Z"
    assert found["before"]["minutes"] == 30 and found["after"]["minutes"] == 30
    assert found["after"]["from_ms"] == int(
        datetime(2026, 11, 3, 12, 5, tzinfo=UTC).timestamp() * 1000
    )
    assert found["complete"] is True and found["ready_at"] is None


def test_baseline_24_hours(settings):
    found = deploycheck.windows(T, settings, now=T + timedelta(hours=2))
    assert found["baseline"]["from"] == "2026-11-02T12:00:00Z"
    assert found["baseline"]["to"] == "2026-11-03T12:00:00Z"


def test_incomplete_after_window_has_ready_at(settings):
    found = deploycheck.windows(T, settings, now=T + timedelta(minutes=20))
    assert found["complete"] is False
    assert found["ready_at"] == "2026-11-03T12:35:00Z"
    assert found["after"]["to"] == "2026-11-03T12:20:00Z"
    assert found["after"]["minutes"] == 15
    early = deploycheck.windows(T, settings, now=T + timedelta(minutes=2))
    assert early["after"]["minutes"] == 0 and early["complete"] is False
