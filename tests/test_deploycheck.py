import json
import re
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
    path.write_text("[tracker]\nkind = \"jira\"\n[tracker.jira]\nsite = 'x'\n")
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
const full = fs.readFileSync(process.argv[2], "utf8");
const script = full.split("// ws:entry")[0].replace(/^import .*$/m, "");
const lib = new Function(script + "\\nreturn { summarize, run };")();

const seen = [];
function answer(tool, attrs) {
  seen.push({ tool, attrs });
  const query = attrs.filter.query;
  const agg = attrs.compute[0].aggregation;
  for (const r of input.rules || []) {
    if (r.tool !== tool) continue;
    if (r.contains && !query.includes(r.contains)) continue;
    if (r.agg ? r.agg !== agg : agg === "pc95") continue;
    if (r.from_iso && r.from_iso !== attrs.filter.from) continue;

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
  process.stdout.write(JSON.stringify(input.show_seen ? { out, seen } : out));
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
    assert status("http_5xx", **{"http_5xx.a": 21}) == "piorou"
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
    got = summarize(tmp_path, settings, {"traffic.b": 49, "errors.a": 40, "p95.a": 900.0})
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
    before, after = found["before"]["from"], found["after"]["from"]
    versions = [
        {"attributes": {"by": {"version": "abc1234"}, "computes": {"c0": 99}}},
        {"attributes": {"by": {"version": "old"}, "computes": {"c0": 1}}},
    ]
    return [
        {"tool": "spans", "agg": "pc95", "from_iso": before, "response": spans_total(200e6)},
        {"tool": "spans", "agg": "pc95", "from_iso": after, "response": spans_total(210e6)},
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


def by_key(queries: list[dict]) -> dict:
    return {(q["check"], q["window"], q["tool"]): q for q in queries}


def test_classic_queries_cover_every_check_with_exact_arguments(settings):
    queries = deploycheck.classic_queries(settings, "bff", "sandbox", at=None, now=NOW)
    found = by_key(queries)
    assert {q["check"] for q in queries} == set(deploycheck.CHECKS["apm"])
    assert len(queries) == 15
    assert all(set(q) == {"check", "window", "tool", "arguments"} for q in queries)
    assert all("intent" in q["arguments"]["telemetry"] for q in queries)

    base = "service:svc-bff env:env-sbx operation_name:web.request"
    window = {"from": "2026-11-03T11:30:00Z", "to": "2026-11-03T12:00:00Z"}
    count = [{"aggregation": "COUNT", "field": "*", "output": "count"}]
    traffic = found[("traffic", "before", "aggregate_spans")]["arguments"]
    assert {k: v for k, v in traffic.items() if k != "telemetry"} == {
        "query": base,
        "computes": count,
        **window,
    }
    after = {"from": "2026-11-03T12:05:00Z", "to": "2026-11-03T12:35:00Z"}
    errors = found[("errors", "after", "aggregate_spans")]["arguments"]
    assert (errors["query"], errors["computes"]) == (base + " status:error", count)
    assert {"from": errors["from"], "to": errors["to"]} == after
    five = found[("http_5xx", "after", "aggregate_spans")]["arguments"]
    assert five["query"] == base + " @http.status_code:[500 TO 599]"
    p95 = found[("p95", "before", "aggregate_spans")]["arguments"]
    assert p95["computes"] == [
        {"aggregation": "P95", "field": "@duration", "output": "p95_duration_ns"}
    ]
    logs = found[("error_logs", "after", "analyze_datadog_logs")]["arguments"]
    assert logs["sql_query"] == "SELECT count(*) FROM logs"
    assert logs["filter"] == "service:svc-bff env:env-sbx status:error"
    assert {"from": logs["from"], "to": logs["to"]} == after
    baseline = found[("new_errors", "baseline", "analyze_datadog_logs")]["arguments"]
    assert baseline["from"] == "2026-11-02T12:00:00Z" and baseline["to"] == "2026-11-03T12:00:00Z"
    assert baseline["extra_columns"] == [{"name": "@error.kind", "type": "varchar"}]
    assert "GROUP BY" in baseline["sql_query"] and "LIMIT 50" in baseline["sql_query"]
    spans = found[("new_errors", "after", "aggregate_spans")]["arguments"]
    assert spans["group_by"] == {"fields": ["resource_name", "@error.type"], "limit": 50}
    assert spans["query"] == base + " status:error"
    version = found[("version", "after", "aggregate_spans")]["arguments"]
    assert version["group_by"] == {"fields": ["version"], "limit": 50}


def test_classic_queries_rum_and_logs_kinds(tmp_path, argocd, monkeypatch):
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
    order = '["shared", "front", "worker"]'
    write_config(tmp_path, monkeypatch, config_text(argocd, order=order, extra_service=extra))
    loaded = deploycheck.load_settings()
    front = deploycheck.classic_queries(loaded, "front", "sandbox", at=None, now=NOW)
    assert {q["tool"] for q in front} == {"aggregate_rum_events"}
    assert {q["check"] for q in front} == set(deploycheck.CHECKS["rum"])
    views = by_key(front)[("traffic", "before", "aggregate_rum_events")]["arguments"]
    assert views["query"] == "service:svc-front env:env-sbx @type:view"
    worker = deploycheck.classic_queries(loaded, "worker", "sandbox", at=None, now=NOW)
    assert {q["tool"] for q in worker} == {"analyze_datadog_logs"}
    assert {q["check"] for q in worker} == set(deploycheck.CHECKS["logs"])


def test_entry_section_references_only_the_known_sdk_surface(settings):
    entry = script_for(settings).split("// ws:entry")[1]
    used = set(re.findall(r"\bsdk\.[\w.]+", entry))
    assert used == set()
    assert set(re.findall(r"\b(?:client|v2)\.[\w.]+", entry)) == {
        "client.createConfiguration",
        "v2.SpansApi",
        "v2.LogsApi",
        "v2.RUMApi",
    }
    lines = script_for(settings).splitlines()
    imports = [line for line in lines if line.startswith("import ")]
    assert imports == ['import { client, v2 } from "@datadog/datadog-api-client";']
    assert lines.index(imports[0]) < next(
        i for i, line in enumerate(lines) if line.startswith("const P")
    )
    assert set(re.findall(r"\b(?:spansApi|logsApi|rumApi)\.\w+", entry)) == {
        "spansApi.aggregateSpans",
        "logsApi.aggregateLogs",
        "rumApi.aggregateRUMEvents",
    }


def test_settings_min_extra_errors_default_and_override(tmp_path, argocd, monkeypatch):
    write_config(tmp_path, monkeypatch, config_text(argocd))
    assert deploycheck.load_settings().min_extra_errors == 10
    text = config_text(argocd).replace(
        "min_requests = 50", "min_requests = 50\nmin_extra_errors = 25"
    )
    write_config(tmp_path, monkeypatch, text)
    loaded = deploycheck.load_settings()
    assert loaded.min_extra_errors == 25
    assert params_of(script_for(loaded))["min_extra_errors"] == 25


def test_plan_warns_without_dd_version_and_about_an_informational_tag(settings, argocd):
    values = argocd / "envs" / "svc-x.yaml"
    now = T + timedelta(hours=1)
    values.write_text("image:\n  tag: only1\n")
    warnings = deploycheck.plan(settings, "sandbox", at=None, only=["bff"], now=now)["warnings"]
    assert len(warnings) == 1 and "DD_VERSION" in warnings[0] and "bff" in warnings[0]

    values.write_text("sidecar:\n  tag: side1\nimage:\n  repository: r\n  tag: main1\n")
    found = deploycheck.deploy_of(argocd, "envs/svc-x.yaml")
    assert found["tag"] == "main1" and found["tag_from_image"] is True

    values.write_text("other:\n  tag: z9\nDD_VERSION: v1\n")
    warnings = deploycheck.plan(settings, "sandbox", at=None, only=["bff"], now=now)["warnings"]
    assert len(warnings) == 1 and "informational" in warnings[0]

    values.write_text("replicas: 2\n")
    warnings = deploycheck.plan(settings, "sandbox", at=None, only=["bff"], now=now)["warnings"]
    assert any("DD_VERSION" in w for w in warnings) and any("no image tag" in w for w in warnings)

    (argocd / "envs" / "svc-x.yaml").unlink()
    warnings = deploycheck.plan(settings, "sandbox", at=None, only=["bff"], now=now)["warnings"]
    assert any("DD_VERSION" in w for w in warnings)


@needs_node
def test_relative_rise_needs_the_extra_errors_for_piorou(tmp_path, settings):
    def status(name, **raw):
        return summarize(tmp_path, settings, raw)["checks"][name]["status"]

    # 1% -> 1.6% is up 60% but only 6 extra errors: atencao; 11 extra: piorou
    assert status("http_5xx", **{"http_5xx.a": 16}) == "atencao"
    assert status("http_5xx", **{"http_5xx.a": 20}) == "piorou"
    assert status("http_5xx", **{"http_5xx.a": 15}) == "ok"
    assert status("errors", **{"errors.a": 31}) == "piorou"
    assert status("errors", **{"errors.b": 2, "errors.a": 4}) == "atencao"
    assert status("error_logs", **{"error_logs.b": 10, "error_logs.a": 16}) == "atencao"
    assert status("error_logs", **{"error_logs.b": 10, "error_logs.a": 20}) == "piorou"


@needs_node
def test_min_extra_errors_is_configurable(tmp_path, argocd, monkeypatch):
    text = config_text(argocd).replace(
        "min_requests = 50", "min_requests = 50\nmin_extra_errors = 3"
    )
    write_config(tmp_path, monkeypatch, text)
    loaded = deploycheck.load_settings()
    got = summarize(tmp_path, loaded, {"http_5xx.a": 16})
    assert got["checks"]["http_5xx"]["status"] == "piorou"


@needs_node
def test_version_check_is_gated_by_min_requests(tmp_path, settings):
    got = summarize(tmp_path, settings, {"version.a": {"abc1234": 10, "old": 30}})
    assert got["checks"]["version"]["status"] == "sem_dados"
    assert got["version_share_pct"] is None


@needs_node
def test_version_without_the_facet_counts_as_sem_versao(tmp_path, settings):
    rules = spans_rules(settings)
    unusable = {"data": [{"attributes": {"by": {}, "computes": {"c0": 100}}}]}
    rules[3] = {"tool": "spans", "grouped": True, "response": unusable}
    got = node_run(tmp_path, script_for(settings), {"op": "run", "rules": rules})
    version = got["checks"]["version"]
    assert version["status"] == "atencao"
    assert got["version_share_pct"] == 0.0
    assert got["checks"]["traffic"]["status"] == "ok"


@needs_node
def test_traffic_drop_and_short_after_window(tmp_path, settings):
    def traffic(**raw):
        return summarize(tmp_path, settings, raw)["checks"]["traffic"]["status"]

    assert traffic(**{"traffic.a": 499}) == "piorou"
    assert traffic(**{"traffic.a": 500}) == "ok"
    assert traffic(**{"traffic.a": 60}) == "piorou"
    assert traffic(**{"traffic.b": 49, "traffic.a": 5}) == "sem_dados"


@needs_node
def test_short_after_window_is_atencao_and_empty_window_is_sem_dados(tmp_path, settings):
    def checks(minutes_ago):
        script = deploycheck.build_script(
            settings, "bff", "sandbox", at=NOW - timedelta(minutes=minutes_ago), now=NOW
        )
        payload = {"op": "summarize", "raw": BASE_RAW, "failed": {}}
        return node_run(tmp_path, script, payload)["checks"]

    assert checks(7)["traffic"]["status"] == "atencao"
    empty = checks(5)
    assert empty["traffic"]["status"] == "sem_dados"
    assert empty["error_logs"]["status"] == "sem_dados"


@needs_node
def test_requests_use_the_documented_shapes(tmp_path, settings):
    payload = {"op": "run", "rules": spans_rules(settings), "show_seen": True}
    seen = node_run(tmp_path, script_for(settings), payload)["seen"]
    spans = [item["attrs"] for item in seen if item["tool"] == "spans"]
    assert spans
    for attrs in spans:
        compute = attrs["compute"][0]
        assert "type" not in compute
        assert compute["metric"] in {"*", "@duration"}
        for group in attrs.get("groupBy", []):
            if "sort" in group:
                assert group["sort"] == {
                    "aggregation": "count", "metric": "*", "order": "desc", "type": "measure"
                }  # fmt: skip
    found = deploycheck.windows(T, settings, NOW)
    froms = {attrs["filter"]["from"] for attrs in spans}
    assert froms >= {found["before"]["from"], found["after"]["from"]}
    assert all(attrs["filter"]["to"].endswith("Z") for attrs in spans)


def test_skill_names_the_tool_and_the_rules():
    skill = (Path(__file__).parent.parent / "skills" / "deploy-check" / "SKILL.md").read_text()
    for needle in (
        "mcp__plugin_engineering_datadog__execute_code",
        "execute_code_write",
        "ddsetup",
        'telemetry: {intent: "..."}',
        "search_datadog_sdk",
        "override",
        "span counts",
    ):
        assert needle in skill
    assert "do not search the SDK" not in skill
