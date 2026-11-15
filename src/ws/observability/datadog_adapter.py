"""The Datadog adapter of the observability port.

`request` fills the `datadog_count.js` template with the whole document as one JSON literal, so a
query can never leave the literal. `fallback` lists the classic-tool calls that answer the same
counts. Nothing here calls Datadog.
"""

import json
from importlib import resources

PARAMS_MARKER = "/*ws:params*/null"
TEMPLATE = "datadog_count.js"
COUNT_SQL = "SELECT count(*) FROM logs"


def _template() -> str:
    return resources.files("ws.data").joinpath(TEMPLATE).read_text(encoding="utf-8")


def _call(item: dict) -> dict:
    window = {"from": item["from"], "to": item["to"]}
    signal = item["signal"]
    if signal == "traces":
        arguments = {
            "query": item["query"],
            "computes": [{"aggregation": "COUNT", "field": "*", "output": "count"}],
            **window,
        }
        return {"check": item["check"], "tool": "aggregate_spans", "arguments": arguments}
    if signal == "logs":
        arguments = {"sql_query": COUNT_SQL, "filter": item["query"], **window}
        return {"check": item["check"], "tool": "analyze_datadog_logs", "arguments": arguments}
    if signal == "metrics":
        return {
            "check": item["check"],
            "tool": "get_datadog_metric",
            "arguments": {"queries": [item["query"]], **window},
            "note": "sum the points",
        }
    raise ValueError(f"unknown signal: {signal!r}")


class Datadog:
    kind = "datadog"
    tool = "execute_code"

    def request(self, document: dict) -> str:
        template = _template()
        if template.count(PARAMS_MARKER) != 1:
            raise ValueError(f"the template must hold {PARAMS_MARKER!r} exactly once")
        literal = json.dumps(document, ensure_ascii=True)
        return template.replace(PARAMS_MARKER, literal)

    def fallback(self, document: dict) -> list[dict]:
        return [_call(item) for item in document["counts"]]


def from_config(table: dict) -> Datadog:
    return Datadog()
