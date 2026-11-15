import json
import shutil
import subprocess

import pytest

from ws.observability import open_observability, providers
from ws.observability.datadog_adapter import PARAMS_MARKER, TEMPLATE, Datadog, from_config
from ws.observability.port import Observability, Setup

WEIRD = 'a"b\\c é</script>*/ `x` ${1+1}\n\u2028\u2029end'


def count(check, signal, query="service:x", hash_="aaaaaaaaaaaa", **extra):
    return {
        "check": check,
        "signal": signal,
        "query": query,
        "from": extra.get("from", "2026-12-09T00:00:00Z"),
        "to": extra.get("to", "2026-12-10T00:00:00Z"),
        "hash": hash_,
    }


def document(*counts):
    return {"version": 1, "task": "TS-5", "day": "2026-12-09", "counts": list(counts)}


def template_text():
    from importlib import resources

    return resources.files("ws.data").joinpath(TEMPLATE).read_text(encoding="utf-8")


def literal_line(program):
    lines = [line for line in program.splitlines() if line.startswith("const P = ")]
    assert len(lines) == 1
    return lines[0]


def test_request_embeds_one_json_literal_and_nothing_else():
    doc = document(count("c1", "traces"))
    program = Datadog().request(doc)
    line = literal_line(program)
    literal = line[len("const P = ") : -1]
    assert json.loads(literal) == doc
    assert program.replace(literal, PARAMS_MARKER) == template_text()


def test_request_escapes_queries():
    doc = document(count("c1", "logs", query=WEIRD))
    program = Datadog().request(doc)
    line = literal_line(program)
    assert line.isascii()
    assert json.loads(line[len("const P = ") : -1]) == doc
    assert len(program.splitlines()) == len(template_text().splitlines())


def test_request_needs_the_marker_once(monkeypatch):
    import ws.observability.datadog_adapter as adapter

    monkeypatch.setattr(adapter, "_template", lambda: "x")
    with pytest.raises(ValueError):
        Datadog().request(document())
    monkeypatch.setattr(adapter, "_template", lambda: PARAMS_MARKER + PARAMS_MARKER)
    with pytest.raises(ValueError):
        Datadog().request(document())


def test_fallback_calls_per_signal():
    doc = document(
        count("c1", "traces", query="q1"),
        count("c2", "logs", query="q2", **{"from": "2026-12-08T00:00:00Z"}),
        count("c3", "metrics", query="q3"),
    )
    calls = Datadog().fallback(doc)
    assert [c["tool"] for c in calls] == [
        "aggregate_spans",
        "analyze_datadog_logs",
        "get_datadog_metric",
    ]
    assert [c["check"] for c in calls] == ["c1", "c2", "c3"]
    spans, logs, metric = (c["arguments"] for c in calls)
    assert {key: value for key, value in spans.items() if key != "telemetry"} == {
        "query": "q1",
        "computes": [{"aggregation": "COUNT", "field": "*", "output": "count"}],
        "from": "2026-12-09T00:00:00Z",
        "to": "2026-12-10T00:00:00Z",
    }
    assert logs["sql_query"] == "SELECT count(*) FROM logs"
    assert logs["filter"] == "q2"
    assert logs["from"] == "2026-12-08T00:00:00Z"
    assert metric["queries"] == [{"query": "q3", "aggregator": "sum"}]
    assert metric["response_format"] == "scalar"
    for arguments in (spans, logs, metric):
        assert arguments["telemetry"]["intent"]


def test_open_observability_by_provider(tmp_path, monkeypatch):
    monkeypatch.setenv("WS_CONFIG_DIR", str(tmp_path))
    (tmp_path / "config.toml").write_text('[observability]\nprovider = "datadog"\n')
    found = open_observability()
    assert isinstance(found, Observability)
    assert found.tool == "execute_code"
    assert providers() == ("datadog",)


def test_open_observability_unknown_lists_datadog(tmp_path, monkeypatch):
    monkeypatch.setenv("WS_CONFIG_DIR", str(tmp_path))
    (tmp_path / "config.toml").write_text('[observability]\nprovider = "nope"\n')
    with pytest.raises(Setup, match="datadog"):
        open_observability()


def test_template_holds_each_guard():
    text = template_text()
    for guard in (
        '"partial result: timeout"',
        '"metric query failed"',
        '"unexpected response"',
        'meta.status === "timeout"',
        "response.errors",
        '"HTTP "',
    ):
        assert guard in text


def test_from_config_returns_adapter():
    assert from_config({"provider": "datadog"}).kind == "datadog"


needs_node = pytest.mark.skipif(shutil.which("node") is None, reason="node is not installed")

HARNESS = """\
const fs = require("fs");
const input = JSON.parse(fs.readFileSync(0, "utf8"));
const full = fs.readFileSync(process.argv[2], "utf8");
const script = full.split("// ws:entry")[0].replace(/^import .*$/m, "");
const lib = new Function(script + "\\nreturn { run };")();
const seen = [];
function answer(kind, attrs) {
  seen.push({ kind, attrs });
  const query = attrs.filter ? attrs.filter.query : "";
  for (const r of input.rules || []) {
    if (r.kind !== kind) continue;
    if (r.contains && !query.includes(r.contains)) continue;
    if (r.throw) throw Object.assign(new Error(r.throw), r.code ? { code: r.code } : {});
    return r.response;
  }
  return { data: [] };
}
const api = {
  spans: async (a) => answer("spans", a),
  logs: async (a) => answer("logs", a),
  metrics: async (a) => answer("metrics", a),
};
(async () => {
  const result = await lib.run(api);
  process.stdout.write(JSON.stringify({ result, seen }));
})().catch((error) => { console.error(error); process.exit(1); });
"""


def node_run(tmp_path, doc, rules):
    (tmp_path / "harness.js").write_text(HARNESS)
    (tmp_path / "program.js").write_text(Datadog().request(doc))
    result = subprocess.run(
        ["node", str(tmp_path / "harness.js"), str(tmp_path / "program.js")],
        input=json.dumps({"rules": rules}),
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stderr
    return json.loads(result.stdout)


def bucket(value):
    return {"data": {"buckets": [{"computes": {"c0": value}}]}}


@needs_node
def test_program_returns_an_observability_result(tmp_path):
    doc = document(count("c1", "traces", query="t", hash_="111111111111"),
                   count("c2", "logs", query="l", hash_="222222222222"))  # fmt: skip
    out = node_run(
        tmp_path,
        doc,
        [
            {"kind": "spans", "response": bucket(0)},
            {"kind": "logs", "response": bucket(3)},
        ],
    )["result"]
    assert out["version"] == 1
    assert out["task"] == "TS-5"
    assert out["day"] == "2026-12-09"
    assert out["provider"] == "datadog"
    assert out["failed"] == []
    by_check = {c["check"]: c for c in out["counts"]}
    assert by_check["c1"]["value"] == 0
    assert by_check["c1"]["hash"] == "111111111111"
    assert by_check["c2"]["value"] == 3
    assert by_check["c2"]["hash"] == "222222222222"
    for item in out["counts"]:
        assert item["started"] <= item["finished"]


@needs_node
def test_program_one_failed_query_keeps_the_others(tmp_path):
    doc = document(count("c1", "traces"), count("c2", "logs"))
    out = node_run(
        tmp_path,
        doc,
        [
            {"kind": "spans", "response": bucket(7)},
            {"kind": "logs", "throw": "boom"},
        ],
    )["result"]
    assert out["failed"] == [{"check": "c2", "reason": "boom"}]
    assert [c["check"] for c in out["counts"]] == ["c1"]
    assert out["counts"][0]["value"] == 7


@needs_node
def test_program_metrics_sum(tmp_path):
    doc = document(count("c1", "metrics"))
    response = {
        "data": {
            "attributes": {
                "columns": [
                    {"type": "group", "values": [["a"], ["b"]]},
                    {"type": "number", "values": [2, 3]},
                    {"type": "number", "values": [9, 9]},
                ]
            }
        }
    }
    out = node_run(tmp_path, doc, [{"kind": "metrics", "response": response}])
    assert out["result"]["counts"][0]["value"] == 5
    sent = out["seen"][0]["attrs"]
    assert sent["queries"][0]["aggregator"] == "sum"


@needs_node
def test_program_uses_each_count_window(tmp_path):
    doc = document(
        count("c1", "traces", **{"from": "2026-12-01T00:00:00Z", "to": "2026-12-02T00:00:00Z"}),
        count("c2", "logs", **{"from": "2026-12-03T00:00:00Z", "to": "2026-12-04T00:00:00Z"}),
    )
    seen = node_run(tmp_path, doc, [])["seen"]
    windows = {s["kind"]: (s["attrs"]["filter"]["from"], s["attrs"]["filter"]["to"]) for s in seen}
    assert windows["spans"] == ("2026-12-01T00:00:00Z", "2026-12-02T00:00:00Z")
    assert windows["logs"] == ("2026-12-03T00:00:00Z", "2026-12-04T00:00:00Z")


@needs_node
def test_injection_through_query_is_inert(tmp_path):
    doc = document(count("c1", "traces", query=WEIRD))
    out = node_run(tmp_path, doc, [{"kind": "spans", "response": bucket(1)}])
    assert out["seen"][0]["attrs"]["filter"]["query"] == WEIRD
    assert out["result"]["counts"][0]["value"] == 1


@needs_node
def test_program_metrics_window_is_milliseconds(tmp_path):
    doc = document(
        count("c1", "metrics", **{"from": "2026-12-01T00:00:00Z", "to": "2026-12-02T00:00:00Z"})
    )
    response = {"data": {"attributes": {"columns": []}}}
    sent = node_run(tmp_path, doc, [{"kind": "metrics", "response": response}])["seen"][0]["attrs"]
    assert sent["from"] == 1796083200000
    assert sent["to"] == 1796169600000


@needs_node
@pytest.mark.parametrize("signal", ["traces", "logs"])
def test_program_timeout_is_a_failure_not_zero(tmp_path, signal):
    kind = "spans" if signal == "traces" else "logs"
    response = {"data": {"buckets": []}, "meta": {"status": "timeout"}}
    out = node_run(tmp_path, document(count("c1", signal)), [{"kind": kind, "response": response}])
    assert out["result"]["counts"] == []
    assert out["result"]["failed"] == [{"check": "c1", "reason": "partial result: timeout"}]


@needs_node
@pytest.mark.parametrize(
    ("response", "reason"),
    [
        (
            {"errors": [{"title": "x"}], "data": {"attributes": {"columns": []}}},
            "metric query failed",
        ),
        ({"data": {}}, "unexpected response"),
        (
            {"data": {"attributes": {"columns": [{"type": "group", "values": [["a"]]}]}}},
            "unexpected response",
        ),
        ({}, "unexpected response"),
    ],
)
def test_program_metrics_bad_answer_is_a_failure(tmp_path, response, reason):
    out = node_run(
        tmp_path, document(count("c1", "metrics")), [{"kind": "metrics", "response": response}]
    )
    assert out["result"]["counts"] == []
    assert out["result"]["failed"] == [{"check": "c1", "reason": reason}]


@needs_node
def test_program_failure_with_code_hides_the_body(tmp_path):
    out = node_run(
        tmp_path,
        document(count("c1", "logs", query="secret")),
        [{"kind": "logs", "throw": "x", "code": 403}],
    )
    assert out["result"]["failed"] == [{"check": "c1", "reason": "HTTP 403"}]


@needs_node
def test_program_failure_with_text_code_keeps_the_message(tmp_path):
    out = node_run(
        tmp_path,
        document(count("c1", "logs")),
        [{"kind": "logs", "throw": "socket hang up", "code": "ECONNRESET"}],
    )
    assert out["result"]["failed"] == [{"check": "c1", "reason": "socket hang up"}]
