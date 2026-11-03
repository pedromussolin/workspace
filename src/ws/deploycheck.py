"""Deploy check (part D of the session automations): the deploy plan, the time windows and the
Datadog program that `execute_code` runs.

Everything deterministic lives here: the services in deploy order, the deploy moment read from the
local argocd repo, the windows, the JavaScript program (a versioned template with one JSON literal
of parameters) and the classic-tool queries used as a fallback. Nothing here calls Datadog, pulls a
repo or writes anywhere.
"""

import json
import re
import subprocess
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from importlib import resources
from pathlib import Path

from ws.config import config_dir
from ws.userconfig import ConfigInvalid, load_table

KINDS = ("apm", "rum", "logs")
CHECKS = {
    "apm": ["traffic", "errors", "http_5xx", "p95", "error_logs", "new_errors", "version"],
    "rum": ["traffic", "errors", "new_errors", "version"],
    "logs": ["error_logs", "new_errors"],
}
PARAMS_MARKER = "/*ws:params*/null"
DEFAULT_WINDOW_MINUTES = 30
DEFAULT_SETTLE_MINUTES = 5
DEFAULT_BASELINE_HOURS = 24
DEFAULT_MIN_REQUESTS = 50
DEFAULT_VERSION_FACET = "version"
SIGNATURE_LIMIT = 50
TAG_LINE = re.compile(r"^\s*tag:\s*[\"']?([^\"'\s#]+)", re.MULTILINE)
DD_VERSION_LIST = re.compile(
    r"name:\s*[\"']?DD_VERSION[\"']?\s*\n\s*value:\s*[\"']?([^\"'\s#]+)", re.MULTILINE
)
DD_VERSION_MAP = re.compile(r"^\s*DD_VERSION:\s*[\"']?([^\"'\s#]+)", re.MULTILINE)


class DeployCheckError(Exception):
    """The plan cannot be built: unknown env or service, or no deploy found."""


@dataclass(frozen=True)
class ServiceSettings:
    key: str
    service: str
    kind: str
    argocd: Path
    values: dict[str, str]
    span_filter: str | None = None
    version_facet: str = DEFAULT_VERSION_FACET


@dataclass(frozen=True)
class DeployCheckSettings:
    order: tuple[str, ...]
    env_tags: dict[str, str]
    services: dict[str, ServiceSettings]
    window_minutes: int = DEFAULT_WINDOW_MINUTES
    settle_minutes: int = DEFAULT_SETTLE_MINUTES
    baseline_hours: int = DEFAULT_BASELINE_HOURS
    min_requests: int = DEFAULT_MIN_REQUESTS


def _text(value: object, where: str) -> str:
    if not isinstance(value, str) or not value:
        raise ConfigInvalid(f"{where} must be a non-empty string")
    return value


def _positive(table: dict, key: str, default: int) -> int:
    value = table.get(key, default)
    if isinstance(value, bool) or not isinstance(value, int) or value < 1:
        raise ConfigInvalid(f"deploy_check.{key} must be a positive integer")
    return value


def _string_map(value: object, where: str) -> dict[str, str]:
    if not isinstance(value, dict) or not value:
        raise ConfigInvalid(f"{where} must be a non-empty table")
    return {_text(k, where): _text(v, f"{where}.{k}") for k, v in value.items()}


def _service(key: str, table: object) -> ServiceSettings:
    where = f"deploy_check.services.{key}"
    if not isinstance(table, dict):
        raise ConfigInvalid(f"{where} must be a table")
    kind = table.get("kind", "apm")
    if kind not in KINDS:
        raise ConfigInvalid(f"{where}.kind must be one of {', '.join(KINDS)}")
    span_filter = table.get("span_filter")
    if span_filter is not None:
        span_filter = _text(span_filter, f"{where}.span_filter")
    return ServiceSettings(
        key=key,
        service=_text(table.get("service"), f"{where}.service"),
        kind=kind,
        argocd=Path(_text(table.get("argocd"), f"{where}.argocd")).expanduser(),
        values=_string_map(table.get("values"), f"{where}.values"),
        span_filter=span_filter,
        version_facet=_text(
            table.get("version_facet", DEFAULT_VERSION_FACET), f"{where}.version_facet"
        ),
    )


def load_settings() -> DeployCheckSettings:
    path = config_dir() / "config.toml"
    table = load_table("deploy_check")
    order = table.get("order")
    if not isinstance(order, list) or not order:
        raise ConfigInvalid(f"{path}: deploy_check.order must be a non-empty list")
    order = [_text(item, f"{path}: deploy_check.order item") for item in order]
    raw_services = table.get("services")
    if not isinstance(raw_services, dict) or not raw_services:
        raise ConfigInvalid(f"{path}: deploy_check.services must be a non-empty table")
    for key in order:
        if key not in raw_services:
            raise ConfigInvalid(
                f"{path}: deploy_check.order names {key}, which has no services entry"
            )
    try:
        env_tags = _string_map(table.get("env_tags"), "deploy_check.env_tags")
        services = {key: _service(key, raw_services[key]) for key in order}
        return DeployCheckSettings(
            order=tuple(order),
            env_tags=env_tags,
            services=services,
            window_minutes=_positive(table, "window_minutes", DEFAULT_WINDOW_MINUTES),
            settle_minutes=_positive(table, "settle_minutes", DEFAULT_SETTLE_MINUTES),
            baseline_hours=_positive(table, "baseline_hours", DEFAULT_BASELINE_HOURS),
            min_requests=_positive(table, "min_requests", DEFAULT_MIN_REQUESTS),
        )
    except ConfigInvalid as error:
        raise ConfigInvalid(f"{path}: {error}") from None


def _iso(moment: datetime) -> str:
    return moment.astimezone(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


def _ms(moment: datetime) -> int:
    return int(moment.timestamp() * 1000)


def _git(repo: Path, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["git", "-C", str(repo), *args], capture_output=True, text=True, check=False
    )


def _behind(repo: Path) -> int:
    result = _git(repo, "rev-list", "--count", "HEAD..@{upstream}")
    return int(result.stdout) if result.returncode == 0 and result.stdout.strip().isdigit() else 0


def _read_values(repo: Path, values: str) -> dict:
    try:
        text = (repo / values).read_text(encoding="utf-8")
    except OSError:
        return {"tag": None, "dd_version": None}
    tag = TAG_LINE.search(text)
    dd = DD_VERSION_LIST.search(text) or DD_VERSION_MAP.search(text)
    return {"tag": tag.group(1) if tag else None, "dd_version": dd.group(1) if dd else None}


def deploy_of(argocd: Path, values: str) -> dict:
    """The last commit that touched `values`: sha, committer time (UTC), subject, tag, DD_VERSION.

    `behind` counts the commits the last fetch saw upstream and this repo lacks; `ws` never pulls.
    """
    result = _git(argocd, "log", "-1", "--format=%H%x00%cI%x00%s", "--", values)
    if result.returncode != 0:
        raise DeployCheckError(f"git log failed in the argocd repo: {result.stderr.strip()}")
    if not result.stdout.strip():
        raise DeployCheckError(f"no commit touches {values} in the argocd repo")
    sha, committed, subject = result.stdout.rstrip("\n").split("\x00", 2)
    return {
        "sha": sha,
        "time": _iso(datetime.fromisoformat(committed)),
        "subject": subject,
        **_read_values(argocd, values),
        "behind": _behind(argocd),
    }


def _window(start: datetime, end: datetime) -> dict:
    return {
        "from": _iso(start),
        "to": _iso(end),
        "from_ms": _ms(start),
        "to_ms": _ms(end),
        "minutes": max(0, int((end - start).total_seconds() // 60)),
    }


def windows(t: datetime, settings: DeployCheckSettings, now: datetime) -> dict:
    """Before [T-w, T), after [T+settle, T+settle+w) cut at `now`, baseline [T-baseline, T)."""
    span = timedelta(minutes=settings.window_minutes)
    after_from = t + timedelta(minutes=settings.settle_minutes)
    after_to = after_from + span
    complete = now >= after_to
    return {
        "before": _window(t - span, t),
        "after": _window(after_from, after_to if complete else max(after_from, min(now, after_to))),
        "baseline": _window(t - timedelta(hours=settings.baseline_hours), t),
        "complete": complete,
        "ready_at": None if complete else _iso(after_to),
    }


def _utc(moment: datetime) -> datetime:
    return moment.replace(tzinfo=UTC) if moment.tzinfo is None else moment.astimezone(UTC)


def _entry(
    settings: DeployCheckSettings, key: str, env: str, *, at: datetime | None, now: datetime
) -> dict:
    if env not in settings.env_tags:
        known = ", ".join(sorted(settings.env_tags))
        raise DeployCheckError(f"unknown env {env}; the config has env_tags for: {known}")
    service = settings.services.get(key)
    if service is None:
        raise DeployCheckError(f"unknown service key {key}")
    values = service.values.get(env)
    if values is None:
        raise DeployCheckError(f"{key} has no values file for env {env}")
    warnings = []
    if at is None:
        deploy = {**deploy_of(service.argocd, values), "source": "argocd"}
        moment = datetime.fromisoformat(deploy["time"])
        if deploy["behind"]:
            warnings.append(
                f"{key}: the local argocd repo is {deploy['behind']} commit(s) behind its upstream;"
                " pull before trusting the deploy time"
            )
    else:
        moment = _utc(at)
        deploy = {"time": _iso(moment), "source": "at", **_read_values(service.argocd, values)}
    found = windows(moment, settings, _utc(now))
    return {
        "key": key,
        "service": service.service,
        "kind": service.kind,
        "env_tag": settings.env_tags[env],
        "deploy": deploy,
        "windows": found,
        "complete": found["complete"],
        "ready_at": found["ready_at"],
        "checks": CHECKS[service.kind],
        "warnings": warnings,
    }


def plan(
    settings: DeployCheckSettings,
    env: str,
    *,
    at: datetime | None,
    only: list[str] | None,
    now: datetime,
) -> dict:
    keys = list(settings.order)
    if only:
        for key in only:
            if key not in keys:
                raise DeployCheckError(
                    f"unknown service key {key}; the order is: {', '.join(keys)}"
                )
        keys = [key for key in keys if key in only]
    entries = [_entry(settings, key, env, at=at, now=now) for key in keys]
    warnings = [warning for entry in entries for warning in entry.pop("warnings")]
    return {"env": env, "order": list(settings.order), "services": entries, "warnings": warnings}


def _params(
    settings: DeployCheckSettings, key: str, env: str, *, at: datetime | None, now: datetime
) -> dict:
    entry = _entry(settings, key, env, at=at, now=now)
    service = settings.services[key]
    found = entry["windows"]
    return {
        "service": service.service,
        "env_tag": entry["env_tag"],
        "kind": service.kind,
        "span_filter": service.span_filter,
        "version_facet": service.version_facet,
        "expected_version": entry["deploy"]["dd_version"],
        "min_requests": settings.min_requests,
        "checks": entry["checks"],
        "after_complete": found["complete"],
        "windows": {name: found[name] for name in ("before", "after", "baseline")},
    }


def build_script(
    settings: DeployCheckSettings, key: str, env: str, *, at: datetime | None, now: datetime
) -> str:
    """The template with the parameters as one JSON literal; ASCII-escaped, nothing else changes."""
    template = (resources.files("ws") / "data" / "deploy_check.js").read_text(encoding="utf-8")
    if template.count(PARAMS_MARKER) != 1:
        raise DeployCheckError("deploy_check.js must hold exactly one parameters marker")
    literal = json.dumps(_params(settings, key, env, at=at, now=now), ensure_ascii=True)
    return template.replace(PARAMS_MARKER, literal)


def classic_queries(
    settings: DeployCheckSettings, key: str, env: str, *, at: datetime | None, now: datetime
) -> list[dict]:
    """The program's checks as calls to the classic Datadog tools, for when `execute_code` fails.

    Each item is `{"check", "window", "tool", "arguments"}`; the arguments are the tool's own.
    """
    entry = _entry(settings, key, env, at=at, now=now)
    service = settings.services[key]
    found = entry["windows"]
    kind = service.kind
    base = f"service:{service.service} env:{entry['env_tag']}"
    spans_base = " ".join(part for part in (base, service.span_filter) if part)
    entry_base = base if kind == "rum" else spans_base
    entry_tool = "aggregate_rum_events" if kind == "rum" else "aggregate_spans"
    count = [{"aggregation": "COUNT", "field": "*", "output": "count"}]
    out: list[dict] = []

    def add(check: str, window: str, tool: str, **arguments: object) -> None:
        span = found[window]
        intent = f"deploy-check {check}, {window} window, fallback to the classic tools"
        out.append(
            {
                "check": check,
                "window": window,
                "tool": tool,
                "arguments": {
                    **arguments,
                    "from": span["from"],
                    "to": span["to"],
                    "telemetry": {"intent": intent},
                },
            }
        )

    def counted(check: str, tool: str, query: str, names: tuple[str, ...]) -> None:
        for window in names:
            add(check, window, tool, query=query, computes=count)

    def grouped(check: str, tool: str, query: str, fields: list[str], window: str) -> None:
        group = {"fields": fields, "limit": SIGNATURE_LIMIT}
        add(check, window, tool, query=query, computes=count, group_by=group)

    def log_errors(check: str, sql: str, window: str, columns: list[str] | None = None) -> None:
        arguments: dict[str, object] = {"sql_query": sql, "filter": f"{base} status:error"}
        if columns:
            arguments["extra_columns"] = [{"name": name, "type": "varchar"} for name in columns]
        add(check, window, "analyze_datadog_logs", **arguments)

    both = ("before", "after")
    checks = entry["checks"]
    if kind != "logs":
        views = " @type:view" if kind == "rum" else ""
        counted("traffic", entry_tool, entry_base + views, both)
        if "errors" in checks:
            bad = " @type:error" if kind == "rum" else " status:error"
            counted("errors", entry_tool, entry_base + bad, both)
        if "http_5xx" in checks:
            counted("http_5xx", entry_tool, spans_base + " @http.status_code:[500 TO 599]", both)
        if "p95" in checks:
            p95 = [{"aggregation": "P95", "field": "@duration", "output": "p95_duration_ns"}]
            for window in both:
                add("p95", window, "aggregate_spans", query=spans_base, computes=p95)
        if "version" in checks:
            grouped("version", entry_tool, entry_base + views, [service.version_facet], "after")
    if kind != "rum" and "error_logs" in checks:
        for window in both:
            log_errors("error_logs", "SELECT count(*) FROM logs", window)
    if "new_errors" in checks:
        sql = (
            'SELECT "@error.kind", count(*) FROM logs GROUP BY "@error.kind" '
            f"ORDER BY count(*) DESC LIMIT {SIGNATURE_LIMIT}"
        )
        for window in ("after", "baseline"):
            if kind != "rum":
                log_errors("new_errors", sql, window, ["@error.kind"])
            if kind == "apm":
                fields = ["resource_name", "@error.type"]
                query = spans_base + " status:error"
                grouped("new_errors", "aggregate_spans", query, fields, window)
            if kind == "rum":
                fields = ["@error.type", "@view.url_path_group"]
                query = base + " @type:error"
                grouped("new_errors", "aggregate_rum_events", query, fields, window)
    return out
