import json
import shutil
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


NOW = T + timedelta(hours=2)


def script_for(settings, key="bff", env="sandbox", now=NOW):
    return deploycheck.build_script(settings, key, env, at=None, now=now)


def params_line(script: str) -> str:
    lines = [line for line in script.splitlines() if line.startswith("const P = ")]
    assert len(lines) == 1
    return lines[0]


def params_of(script: str) -> dict:
    return json.loads(params_line(script).removeprefix("const P = ").removesuffix(";"))


def write_config(tmp_path: Path, monkeypatch, text: str) -> None:
    cfg = tmp_path / "cfg"
    cfg.mkdir(exist_ok=True)
    monkeypatch.setenv("WS_CONFIG_DIR", str(cfg))
    (cfg / "config.toml").write_text(text)


def test_script_embeds_one_json_literal_and_nothing_else(settings):
    script = script_for(settings)
    template = (Path(deploycheck.__file__).parent / "data" / "deploy_check.js").read_text()
    literal = params_line(script).removeprefix("const P = ").removesuffix(";")
    assert script.replace(literal, "/*ws:params*/null") == template
    params = json.loads(literal)
    assert params["service"] == "svc-bff"
    assert params["env_tag"] == "env-sbx"
    assert params["expected_version"] == "abc1234"
    assert params["min_requests"] == 50
    assert params["windows"]["after"]["from"] == "2026-11-03T12:05:00Z"
    assert params["span_filter"] == "operation_name:web.request"
    assert params["after_complete"] is True


def test_script_escapes_config_values(tmp_path, argocd, monkeypatch):
    text = config_text(argocd).replace(
        "operation_name:web.request", 'a\\"b\\\\c\\u2028é</script>*/'
    )
    write_config(tmp_path, monkeypatch, text)
    script = script_for(deploycheck.load_settings())
    line = params_line(script)
    assert line.isascii()
    assert params_of(script)["span_filter"] == 'a"b\\c é</script>*/'
    assert script.count("\n") == (
        (Path(deploycheck.__file__).parent / "data" / "deploy_check.js").read_text().count("\n")
    )


def test_script_kind_rum_and_logs_choose_their_checks(tmp_path, argocd, monkeypatch):
    extra = f"""
[deploy_check.services.front]
service = "svc-front"
kind = "rum"
argocd = "{argocd}"
values = {{ sandbox = "envs/svc-x.yaml" }}

[deploy_check.services.worker]
service = "svc-worker"
kind = "logs"
argocd = "{argocd}"
values = {{ sandbox = "envs/svc-x.yaml" }}
"""
    order = '["shared", "bff", "front", "worker"]'
    write_config(tmp_path, monkeypatch, config_text(argocd, order=order, extra_service=extra))
    loaded = deploycheck.load_settings()
    checks = {k: params_of(script_for(loaded, k))["checks"] for k in ("bff", "front", "worker")}
    assert checks["bff"] == [
        "traffic", "errors", "http_5xx", "p95", "error_logs", "new_errors", "version",
    ]  # fmt: skip
    assert checks["front"] == ["traffic", "errors", "new_errors", "version"]
    assert checks["worker"] == ["error_logs", "new_errors"]


needs_node = pytest.mark.skipif(shutil.which("node") is None, reason="node is not installed")

HARNESS = """\
const fs = require("fs");
const input = JSON.parse(fs.readFileSync(0, "utf8"));
const script = fs.readFileSync(process.argv[2], "utf8").split("// ws:entry")[0];
const lib = new Function(script + "\\nreturn { summarize, run };")();

function answer(tool, attrs) {
  const query = attrs.filter.query;
  const agg = attrs.compute[0].aggregation;
  for (const r of input.rules || []) {
    if (r.tool !== tool) continue;
    if (r.contains && !query.includes(r.contains)) continue;
    if (r.agg ? r.agg !== agg : agg === "pc95") continue;
    if (r.from_ms && String(r.from_ms) !== attrs.filter.from) continue;
    if (r.grouped !== undefined && Boolean(attrs.groupBy) !== r.grouped) continue;
    if (r.throw) throw new Error(r.throw);
    return r.response;
  }
  return { data: [] };
}
const api = {
  spans: async (a) => answer("spans", a),
  logs: async (a) => answer("logs", a),
  rum: async (a) => answer("rum", a),
};
(async () => {
  const failed = input.failed || {};
  const out = input.op === "run" ? await lib.run(api) : lib.summarize(input.raw, failed);
  process.stdout.write(JSON.stringify(out));
})();
"""


def node_run(tmp_path: Path, script: str, payload: dict) -> dict:
    (tmp_path / "harness.js").write_text(HARNESS)
    (tmp_path / "program.js").write_text(script)
    result = subprocess.run(
        ["node", str(tmp_path / "harness.js"), str(tmp_path / "program.js")],
        input=json.dumps(payload),
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stderr
    return json.loads(result.stdout)


BASE_RAW = {
    "traffic.b": 1000, "traffic.a": 1000,
    "errors.b": 20, "errors.a": 20,
    "http_5xx.b": 10, "http_5xx.a": 10,
    "p95.b": 200.0, "p95.a": 200.0,
    "error_logs.b": 30, "error_logs.a": 30,
    "new_errors_logs.a": [], "new_errors_logs.base": [],
    "new_errors_spans.a": [], "new_errors_spans.base": [],
    "version.a": {"abc1234": 100},
}  # fmt: skip


def summarize(tmp_path, settings, raw=None, failed=None):
    payload = {"op": "summarize", "raw": {**BASE_RAW, **(raw or {})}, "failed": failed or {}}
    return node_run(tmp_path, script_for(settings), payload)


@needs_node
def test_verdict_thresholds(tmp_path, settings):
    assert summarize(tmp_path, settings)["verdict"] == "ok"

    def status(name, **raw):
        return summarize(tmp_path, settings, raw)["checks"][name]["status"]

    # error rate 2% -> 3.1% is up more than 50%; 3.0% is exactly 50% and passes
    assert status("errors", **{"errors.a": 31}) == "piorou"
    assert status("errors", **{"errors.a": 30}) == "ok"
    assert status("http_5xx", **{"http_5xx.a": 16}) == "piorou"
    assert status("http_5xx", **{"http_5xx.a": 15}) == "ok"
    # p95 needs both more than 30% and more than 50 ms
    assert status("p95", **{"p95.a": 261.0}) == "piorou"
    assert status("p95", **{"p95.a": 259.0}) == "ok"
    assert status("p95", **{"p95.b": 100.0, "p95.a": 140.0}) == "ok"
    assert status("error_logs", **{"error_logs.a": 46}) == "piorou"
    assert status("error_logs", **{"error_logs.a": 45}) == "ok"
    # version: 95% passes
    assert status("version", **{"version.a": {"abc1234": 95, "old": 5}}) == "ok"
    assert status("version", **{"version.a": {"abc1234": 90, "old": 10}}) == "atencao"


@needs_node
def test_new_error_signatures(tmp_path, settings):
    new = {"signature": "Timeout | /pay", "count": 3}
    got = summarize(tmp_path, settings, {"new_errors_spans.a": [new]})
    assert got["checks"]["new_errors"]["status"] == "atencao"
    assert got["verdict"] == "atencao"
    assert got["new_errors"] == [{**new, "source": "spans"}]
    big = {**new, "count": 10}
    got = summarize(tmp_path, settings, {"new_errors_logs.a": [big]})
    assert got["checks"]["new_errors"]["status"] == "piorou"
    known = summarize(
        tmp_path, settings, {"new_errors_spans.a": [new], "new_errors_spans.base": [new]}
    )
    assert known["checks"]["new_errors"]["status"] == "ok"


@needs_node
def test_verdict_from_a_zero_base_and_worst_check_wins(tmp_path, settings):
    got = summarize(tmp_path, settings, {"errors.b": 0, "errors.a": 3})
    assert got["checks"]["errors"]["status"] == "atencao"
    got = summarize(tmp_path, settings, {"errors.b": 0, "errors.a": 12, "p95.a": 900.0})
    assert got["checks"]["errors"]["status"] == "piorou"
    assert got["verdict"] == "piorou"


@needs_node
def test_verdict_sem_dados_under_min_requests(tmp_path, settings):
    got = summarize(tmp_path, settings, {"traffic.a": 49, "errors.a": 40, "p95.a": 900.0})
    for name in ("traffic", "errors", "http_5xx", "p95"):
        assert got["checks"][name]["status"] == "sem_dados"
    assert got["verdict"] == "ok"  # the log and version checks still speak
    none = summarize(tmp_path, settings, {"traffic.a": 0, "traffic.b": 0})
    assert none["checks"]["traffic"]["status"] == "sem_dados"


def spans_total(value):
    return {"data": [{"attributes": {"computes": {"c0": value}}}]}


def logs_total(value):
    return {"data": {"buckets": [{"computes": {"c0": value}}]}}


def spans_rules(settings):
    found = deploycheck.windows(T, settings, NOW)
    before, after = found["before"]["from_ms"], found["after"]["from_ms"]
    versions = [
        {"attributes": {"by": {"version": "abc1234"}, "computes": {"c0": 99}}},
        {"attributes": {"by": {"version": "old"}, "computes": {"c0": 1}}},
    ]
    return [
        {"tool": "spans", "agg": "pc95", "from_ms": before, "response": spans_total(200e6)},
        {"tool": "spans", "agg": "pc95", "from_ms": after, "response": spans_total(210e6)},
        {"tool": "spans", "contains": "status:error", "grouped": True, "response": {"data": []}},
        {"tool": "spans", "grouped": True, "response": {"data": versions}},
        {"tool": "spans", "grouped": False, "response": spans_total(1000)},
        {"tool": "logs", "grouped": True, "response": {"data": {"buckets": []}}},
        {"tool": "logs", "grouped": False, "response": logs_total(30)},
    ]  # fmt: skip


@needs_node
def test_partial_results_keep_the_others(tmp_path, settings):
    failing = {"tool": "spans", "contains": "@http.status_code", "throw": "invalid_request: x"}
    rules = [failing, *spans_rules(settings)]
    got = node_run(tmp_path, script_for(settings), {"op": "run", "rules": rules})
    assert got["checks"]["http_5xx"]["status"] == "sem_dados"
    assert "invalid_request" in got["checks"]["http_5xx"]["note"]
    assert got["checks"]["traffic"]["status"] == "ok"
    assert got["checks"]["errors"]["status"] == "ok"
    assert got["checks"]["p95"]["status"] == "ok"
    assert got["checks"]["version"]["status"] == "ok"
    assert got["version_share_pct"] == 99.0
    assert got["verdict"] == "ok"
    assert len(json.dumps(got)) < 2048


@needs_node
def test_run_queries_only_what_the_kind_needs(tmp_path, argocd, monkeypatch):
    extra = f"""
[deploy_check.services.worker]
service = "svc-worker"
kind = "logs"
argocd = "{argocd}"
values = {{ sandbox = "envs/svc-x.yaml" }}
"""
    order = '["shared", "worker"]'
    write_config(tmp_path, monkeypatch, config_text(argocd, order=order, extra_service=extra))
    loaded = deploycheck.load_settings()
    rules = [
        {"tool": "spans", "throw": "spans must not be called for a logs service"},
        {"tool": "logs", "grouped": True, "response": {"data": {"buckets": []}}},
        {"tool": "logs", "grouped": False, "response": logs_total(30)},
    ]
    got = node_run(tmp_path, script_for(loaded, "worker"), {"op": "run", "rules": rules})
    assert sorted(got["checks"]) == ["error_logs", "new_errors"]
    assert got["verdict"] == "ok"
