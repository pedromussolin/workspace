"""Card policy: how a card is filled, in layers (default, company, project), and the engine that
checks a neutral card against it. Design: docs/specs/2026-11-24-card-policy-design.md."""

import copy
import json
import re
import tomllib
from dataclasses import dataclass
from importlib import resources
from pathlib import Path

from ws.config import config_dir
from ws.contracts import check, validate
from ws.project import SLUG_PATTERN
from ws.tracker.vocab import CARD_TYPES
from ws.userconfig import POLICY_NAME, ConfigInvalid, ConfigMissing

STAGES = ("create", "edit", "finish", "audit")
SUBGROUP_TITLE = re.compile(r"\[[^\[\]]{1,60}\] - \S")
NO_SPACE = re.compile(r"\S+")

GROUP_SCHEMA = {
    "type": "object",
    "additionalProperties": False,
    "properties": {
        "values": {"type": "array", "items": {"type": "string"}},
        "required": {"type": "boolean"},
        "skip_when": {"type": "array", "items": {"type": "string"}},
        "derive": {
            "type": "object",
            "additionalProperties": False,
            "properties": {
                "from": {"enum": ["estimate"]},
                "threshold_hours": {"type": "number"},
                "above": {"type": "string"},
                "at_most": {"type": "string"},
                "keep": {"type": "array", "items": {"type": "string"}},
            },
        },
    },
}
"""A category group, checked here because the validator has no schema for keys chosen by the
policy (`additionalProperties` can only be false)."""

DERIVE_REQUIRED = ("from", "threshold_hours", "above", "at_most")
FIELD_ALIASES = {
    "estimate_minutes": "estimate",
    "spent_minutes": "time_spent",
    "add_labels": "labels",
    "remove_labels": "labels",
    "description": "sections",
}
"""Names a draft or a card dict uses for a field, mapped to the name a gap carries."""


@dataclass(frozen=True)
class Policy:
    """The merged policy and, for each top-level key, the layer that last set it."""

    data: dict
    sources: dict[str, str]

    def to_dict(self) -> dict:
        return {**copy.deepcopy(self.data), "sources": dict(self.sources)}

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), ensure_ascii=False, indent=2)


def _category_problems(categories: object, path: str = "$.categories") -> list[str]:
    if not isinstance(categories, dict):
        return []
    problems: list[str] = []
    for name, group in categories.items():
        where = f"{path}.{name}"
        if not NO_SPACE.fullmatch(name):
            problems.append(f"{where}: the group name must be text without whitespace")
        problems.extend(check(group, GROUP_SCHEMA, where))
        if not isinstance(group, dict):
            continue
        values = group.get("values")
        if isinstance(values, list) and all(isinstance(v, str) for v in values):
            if not values:
                problems.append(f"{where}.values: must not be empty")
            for value in values:
                if not NO_SPACE.fullmatch(value):
                    problems.append(f"{where}.values: {value!r} must be text without whitespace")
            if len(set(values)) != len(values):
                problems.append(f"{where}.values: values must be unique")
        derive = group.get("derive")
        threshold = derive.get("threshold_hours") if isinstance(derive, dict) else None
        if isinstance(threshold, int | float) and not isinstance(threshold, bool):
            if threshold <= 0:
                problems.append(f"{where}.derive.threshold_hours: must be greater than 0")
    return problems


def layer_problems(document: object) -> list[str]:
    """Problems of one layer alone: partial layers pass, wrong or unknown content does not."""
    problems = validate(document, "card-policy")
    if not isinstance(document, dict):
        return problems
    problems.extend(_category_problems(document.get("categories")))
    estimate = document.get("estimate")
    padding = estimate.get("padding_percent") if isinstance(estimate, dict) else None
    if isinstance(padding, int | float) and not isinstance(padding, bool) and padding < 0:
        problems.append("$.estimate.padding_percent: must not be negative")
    return problems


def _merged_problems(document: dict) -> list[str]:
    """What only the whole policy can show: a group has values, a derive is complete and its
    tags belong to the group, and a value is in one group only."""
    problems = layer_problems(document)
    categories = document.get("categories", {})
    if not isinstance(categories, dict):
        return problems
    owner: dict[str, str] = {}
    for name, group in categories.items():
        if not isinstance(group, dict):
            continue
        where = f"$.categories.{name}"
        values = group.get("values")
        if not isinstance(values, list):
            problems.append(f"{where}: missing required key values")
            continue
        for value in values:
            if value in owner and owner[value] != name:
                problems.append(f"{where}.values: {value!r} is also in group {owner[value]}")
            owner.setdefault(value, name)
        derive = group.get("derive")
        if not isinstance(derive, dict):
            continue
        for key in DERIVE_REQUIRED:
            if key not in derive:
                problems.append(f"{where}.derive: missing required key {key}")
        for key in ("above", "at_most"):
            if isinstance(derive.get(key), str) and derive[key] not in values:
                problems.append(f"{where}.derive.{key}: {derive[key]!r} is not in values")
        for value in derive.get("keep", []) if isinstance(derive.get("keep"), list) else []:
            if value not in values:
                problems.append(f"{where}.derive.keep: {value!r} is not in values")
    return problems


def _read(text: str, label: str) -> dict:
    try:
        document = tomllib.loads(text)
    except tomllib.TOMLDecodeError as error:
        raise ConfigInvalid(f"{label}: {error}") from None
    problems = layer_problems(document)
    if problems:
        raise ConfigInvalid(f"{label}: invalid card policy: " + "; ".join(problems))
    return document


def _merge(base: dict, over: dict) -> dict:
    out = dict(base)
    for key, value in over.items():
        if isinstance(value, dict) and isinstance(out.get(key), dict):
            out[key] = _merge(out[key], value)
        else:
            out[key] = copy.deepcopy(value)
    return out


def _read_file(path: Path) -> dict:
    try:
        text = path.read_text(encoding="utf-8")
    except UnicodeDecodeError as error:
        raise ConfigInvalid(f"{path}: {error}") from None
    return _read(text, str(path))


def load(config: object, project: str | None, repo_root: Path) -> Policy:
    """The merged policy: default, then the company file `[card] policy` names in config.toml,
    then `projects/<project>/card-policy.toml`.

    `config` is a `UserConfig` (or None: default and project only). A configured name without a
    file raises `ConfigMissing`; an invalid layer or merge raises `ConfigInvalid`.
    """
    default = resources.files("ws") / "data" / "card-policy" / "default.toml"
    layers = [("default", _read(default.read_text(encoding="utf-8"), "default card policy"))]
    name = getattr(config, "card_policy", None)
    if name is not None:
        if not POLICY_NAME.fullmatch(name):
            raise ConfigInvalid(f"card policy name {name!r} is not a valid file name")
        path = config_dir() / "card-policies" / f"{name}.toml"
        if not path.is_file():
            raise ConfigMissing(path, "card policy file")
        layers.append(("company", _read_file(path)))
    if project is not None:
        if not SLUG_PATTERN.fullmatch(project):
            raise ConfigInvalid(f"project {project!r} is not a valid slug")
        path = repo_root / "projects" / project / "card-policy.toml"
        if path.is_file():
            layers.append(("project", _read_file(path)))
    merged: dict = {}
    sources: dict[str, str] = {}
    for source, document in layers:
        merged = _merge(merged, document)
        sources.update({key: source for key in document if key != "version"})
        sources.setdefault("version", source)
    problems = _merged_problems(merged)
    if problems:
        used = ", ".join(source for source, _ in layers)
        raise ConfigInvalid(f"merged card policy ({used}): " + "; ".join(problems))
    return Policy(merged, sources)


def _listed_epics(toml: Path) -> list[str]:
    try:
        epics = tomllib.loads(toml.read_text(encoding="utf-8")).get("epics")
    except (OSError, UnicodeDecodeError, tomllib.TOMLDecodeError):
        return []
    return [e for e in epics if isinstance(e, str)] if isinstance(epics, list) else []


def project_for(item_path: str | None, epic_ref: str | None, repo_root: Path) -> str | None:
    """The project of an item (`projects/<slug>/...`), else the one whose `project.toml` lists
    the epic, else None."""
    if item_path:
        path = Path(item_path)
        if path.is_absolute():
            try:
                path = path.relative_to(repo_root.resolve())
            except ValueError:
                try:
                    path = path.relative_to(repo_root)
                except ValueError:
                    pass
        parts = path.parts
        if len(parts) >= 3 and parts[0] == "projects" and SLUG_PATTERN.fullmatch(parts[1]):
            return parts[1]
    if epic_ref:
        for toml in sorted((repo_root / "projects").glob("*/project.toml")):
            if epic_ref in _listed_epics(toml):
                return toml.parent.name
    return None


def _gap(rule: str, field: str, detail: str, fix: dict | None = None, suggestion=False) -> dict:
    return {
        "rule": rule,
        "field": field,
        "detail": detail,
        "fix": fix or {"needs": "input"},
        "severity": "suggestion" if suggestion else "required",
    }


def _title_gaps(data: dict, card: dict) -> list[dict]:
    title = card.get("title") or ""
    kind = data.get("title", {}).get("format", "epic_prefix")
    if kind == "subgroup":
        if not SUBGROUP_TITLE.match(title):
            return [_gap("title.format", "title", "title must be '[group] - text'")]
        return []
    prefix = card.get("epic_prefix")
    if prefix and not title.startswith(f"[{prefix}] "):
        return [_gap("title.format", "title", f"title must start with '[{prefix}] '")]
    return []


def _section_gaps(data: dict, card: dict) -> list[dict]:
    required = data.get("sections", {}).get(card.get("type"), {}).get("required", [])
    sections = card.get("sections") or {}
    return [
        _gap("sections.required", "sections", f"section '{heading}' is missing or empty")
        for heading in required
        if not str(sections.get(heading) or "").strip()
    ]


def _required_gaps(data: dict, card: dict, applies) -> list[dict]:
    gaps = []
    require = data.get("create", {}).get("require", [])
    skipped = bool(set(data.get("epic", {}).get("skip_when", [])) & set(card.get("labels") or []))
    present = {
        "epic": card.get("epic"),
        "due": card.get("due"),
        "estimate": (card.get("estimate_minutes") or 0) > 0,
        "assignee": card.get("assignee"),
        "reporter": card.get("reporter"),
    }
    for field, value in present.items():
        if field not in require or value or not applies(field):
            continue
        if field == "epic" and (skipped or card.get("type") not in CARD_TYPES):
            continue
        gaps.append(_gap(f"create.require.{field}", field, f"{field} is required"))
    flagged_due = any(gap["field"] == "due" for gap in gaps)
    if (
        data.get("create", {}).get("due_with_sprint")
        and card.get("sprint")
        and not card.get("due")
        and not flagged_due
        and (applies("sprint") or applies("due"))
    ):
        gaps.append(_gap("create.due_with_sprint", "due", "a due date is required with a sprint"))
    if (
        skipped
        and card.get("epic")
        and card.get("type") in CARD_TYPES
        and applies("epic", "labels")
    ):
        gaps.append(_gap("epic.skip_when", "epic", "a card with this label must have no epic"))
    return gaps


def _category_gaps(data: dict, card: dict, stage: str, applies) -> list[dict]:
    gaps = []
    labels = list(card.get("labels") or [])
    estimate = card.get("estimate_minutes")
    needs_value = "categories" in data.get("create", {}).get("require", [])
    for name, group in data.get("categories", {}).items():
        values = group["values"]
        found = [v for v in dict.fromkeys(labels) if v in values]
        skipped = bool(set(group.get("skip_when", [])) & set(labels))
        derive = group.get("derive")
        computed = None
        if derive and estimate:
            above = estimate > derive["threshold_hours"] * 60
            computed = derive["above"] if above else derive["at_most"]
        if len(found) > 1 and applies("labels"):
            gaps.append(
                _gap(
                    f"categories.{name}.single",
                    "labels",
                    f"group {name} takes at most one value, found {', '.join(found)}",
                )
            )
        elif (
            len(found) == 1
            and computed
            and not skipped
            and applies("labels", "estimate")
            and found[0] != computed
            and found[0] not in derive.get("keep", [])
        ):
            hours = f"{estimate / 60:g}h"
            gaps.append(
                _gap(
                    f"categories.{name}.derive",
                    "labels",
                    f"group {name}: {found[0]} contradicts the estimate of {hours}; "
                    f"expected {computed}",
                    {"value": computed},
                )
            )
        elif (
            not found
            and stage in ("create", "audit")
            and needs_value
            and group.get("required")
            and not skipped
        ):
            gaps.append(
                _gap(
                    f"categories.{name}.required",
                    "labels",
                    f"group {name} needs exactly one value ({', '.join(values)})",
                    {"value": computed} if computed else None,
                )
            )
    return gaps


def _finish_gaps(data: dict, card: dict) -> list[dict]:
    require = data.get("finish", {}).get("require", [])
    gaps = []
    if "start" in require and not card.get("start"):
        gaps.append(_gap("finish.require.start", "start", "the start date is not set"))
    if "time_spent" in require and (card.get("spent_minutes") or 0) <= 0:
        gaps.append(_gap("finish.require.time_spent", "time_spent", "no time spent is logged"))
    return gaps


def _suggestions(data: dict, card: dict) -> list[dict]:
    if data.get("links", {}).get("bug", {}).get("caused_by") != "suggest":
        return []
    if card.get("type") != "bug":
        return []
    if any(link.get("kind") == "caused_by" for link in card.get("links") or []):
        return []
    return [
        _gap(
            "links.bug.caused_by",
            "links",
            "the bug has no 'caused by' link",
            suggestion=True,
        )
    ]


def evaluate(policy: Policy, card: dict, stage: str) -> list[dict]:
    """The gaps of a neutral card against the policy, for a stage.

    `create` and `audit` check everything; `audit` adds the finish rules of a done card and the
    suggestions. `edit` checks only the rules that touch a field in `card["changed"]` (card or
    draft field names: `estimate`/`estimate_minutes`, `add_labels`/`remove_labels`, `description`).
    `finish` checks only `finish.require`. A gap is `{rule, field, detail, fix, severity}`.
    """
    if stage not in STAGES:
        raise ValueError(f"unknown stage {stage!r}; expected one of {', '.join(STAGES)}")
    data = policy.data
    if stage == "finish":
        return _finish_gaps(data, card)
    changed = {FIELD_ALIASES.get(n, n) for n in card.get("changed") or ()}

    def applies(*fields: str) -> bool:
        return stage != "edit" or bool(changed & set(fields))

    gaps: list[dict] = []
    if applies("title"):
        gaps.extend(_title_gaps(data, card))
    if applies("sections"):
        gaps.extend(_section_gaps(data, card))
    gaps.extend(_required_gaps(data, card, applies))
    gaps.extend(_category_gaps(data, card, stage, applies))
    if stage == "audit":
        if card.get("status") == "done":
            gaps.extend(_finish_gaps(data, card))
        gaps.extend(_suggestions(data, card))
    return gaps
