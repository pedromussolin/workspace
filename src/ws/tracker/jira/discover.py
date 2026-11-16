"""What `ws tracker discover` and `ws people add` print for the user's config.toml."""

import json

from ws.tracker.jira.rules import fold

_TYPE_NAMES = {
    "task": ("tarefa", "task"),
    "bug": ("bug",),
    "hotfix": ("hotfix",),
    "improvement": ("melhoria", "improvement"),
    "feature": ("nova funcao", "new feature"),
    "epic": ("epic", "epico"),
    "initiative": ("iniciativa", "initiative"),
}
_LINK_NAMES = {"blocks": "blocks", "relates": "relates"}


def _quote(text: str) -> str:
    return json.dumps(text, ensure_ascii=False)


def _neutral_type(name: str) -> str | None:
    folded = fold(name)
    for neutral, names in _TYPE_NAMES.items():
        if folded in names:
            return neutral
    return None


def discover_toml(issue_types: list[dict], link_types: list[dict]) -> str:
    """The `[tracker.jira.types]` and `[tracker.jira.links]` blocks; unmapped are commented."""
    mapped: dict[str, str] = {}
    spare: list[str] = []
    for item in issue_types:
        name, type_id = str(item.get("name", "")), str(item.get("id", ""))
        neutral = _neutral_type(name)
        if neutral is None or neutral in mapped:
            spare.append(f"# {_quote(name)} = {_quote(type_id)}")
        else:
            mapped[neutral] = type_id
    lines = ["[tracker.jira.types]"]
    for neutral in _TYPE_NAMES:
        if neutral in mapped:
            lines.append(f"{neutral} = {_quote(mapped[neutral])}")
        else:
            lines.append(f"# {neutral} = ?  (no issue type with a known name)")
    lines.extend(spare)
    found: dict[str, str] = {}
    other: list[str] = []
    for item in link_types:
        name = str(item.get("name", ""))
        neutral = _LINK_NAMES.get(fold(name))
        if neutral is None or neutral in found:
            other.append(f"# {_quote(name)}")
        else:
            found[neutral] = name
    lines += ["", "[tracker.jira.links]"]
    for neutral in _LINK_NAMES.values():
        if neutral in found:
            lines.append(f"{neutral} = {_quote(found[neutral])}")
        else:
            lines.append(f"# {neutral} = ?  (no link type with a known name)")
    lines.extend(other)
    return "\n".join(lines) + "\n"


def people_block(dev_id: str, kind: str, account: str) -> str:
    """The `[people."dev-…"]` table to paste in config.toml; it never carries the e-mail."""
    return f"[people.{_quote(dev_id)}]\n{kind} = {_quote(account)}\n"
