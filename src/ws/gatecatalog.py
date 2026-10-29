"""The MCP catalog of the approval gate: which configured servers it does not know, which tools it
asked about without knowing them, and how to classify them.

`hooks/gate/catalog.json` lists per server the tools that `pass` (never write outside the machine)
and the tools that `ask`. The gate records a tool in neither list in `unclassified.json`. Everything
here only reads Claude Code's files (`ws` never writes them); the one file it writes is the
catalog, in the repo.
"""

import json
import os
import re
import tempfile
from dataclasses import dataclass, field
from pathlib import Path

from ws.config import (
    claude_json_path,
    claude_plugins_dir,
    claude_settings_path,
    data_dir,
    repo_root,
)

LISTS = ("pass", "ask")
TOOL_NAME = re.compile(r"[A-Za-z0-9_.-]+")
PLUGIN_PART = re.compile(r"[^A-Za-z0-9_-]+")
CONNECTOR_PART = re.compile(r"[^A-Za-z0-9]+")
RECORDED_NAME = re.compile(r"[A-Za-z0-9_.-]{1,128}")
RECORDED_DATE = re.compile(r"\d{4}-\d{2}-\d{2}")


class CatalogError(Exception):
    """A request the catalog cannot take; the message says why."""


def catalog_path() -> Path:
    return repo_root() / "hooks" / "gate" / "catalog.json"


def unclassified_path() -> Path:
    return data_dir() / "gate" / "unclassified.json"


def _json(path: Path) -> object:
    try:
        return json.loads(path.read_bytes())
    except (OSError, ValueError):
        return None


def _dict(value: object) -> dict:
    return value if isinstance(value, dict) else {}


def _server_names(data: dict) -> list[str]:
    """A `.mcp.json` is either the server table itself or has it under `mcpServers`."""
    table = _dict(data.get("mcpServers")) if "mcpServers" in data else data
    return [str(name) for name, config in table.items() if isinstance(config, dict)]


def _plugin_servers(install: Path) -> list[str]:
    names = _server_names(_dict(_json(install / ".mcp.json")))
    manifest = _dict(_json(install / ".claude-plugin" / "plugin.json"))
    declared = manifest.get("mcpServers")
    for item in declared if isinstance(declared, list) else [declared]:
        if isinstance(item, dict):
            names += _server_names({"mcpServers": item})
        elif isinstance(item, str):
            target = (install / item).resolve()
            if target.is_relative_to(install.resolve()):
                names += _server_names(_dict(_json(target)))
    return names


def _plugin_prefixes(settings: Path | None) -> set[str]:
    enabled = _dict(_dict(_json(settings or claude_settings_path())).get("enabledPlugins"))
    installed = _dict(_dict(_json(claude_plugins_dir() / "installed_plugins.json")).get("plugins"))
    prefixes: set[str] = set()
    for key, value in enabled.items():
        if value is not True:
            continue
        plugin = PLUGIN_PART.sub("_", key.split("@")[0])
        entries = installed.get(key)
        for entry in entries if isinstance(entries, list) else []:
            path = _dict(entry).get("installPath")
            if not isinstance(path, str):
                continue
            for server in _plugin_servers(Path(path)):
                prefixes.add(f"plugin_{plugin}_{PLUGIN_PART.sub('_', server)}")
    return prefixes


def _claude_json_prefixes() -> set[str]:
    data = _dict(_json(claude_json_path()))
    names = list(_dict(data.get("mcpServers")))
    for project in _dict(data.get("projects")).values():
        names += list(_dict(_dict(project).get("mcpServers")))
    prefixes = {PLUGIN_PART.sub("_", str(name)) for name in names}
    connected = data.get("claudeAiMcpEverConnected")
    for name in connected if isinstance(connected, list) else []:
        if isinstance(name, str):
            prefixes.add(CONNECTOR_PART.sub("_", name))
    return prefixes


def configured_servers(settings: Path | None = None) -> list[str]:
    """The tool-name prefix (`mcp__<prefix>__<tool>`) of each MCP server this user has, found
    best effort: a file that is missing or unreadable is skipped, config values are never read."""
    return sorted(_plugin_prefixes(settings) | _claude_json_prefixes())


def load_catalog(path: Path | None = None) -> dict:
    path = path or catalog_path()
    data = _json(path)
    if not isinstance(data, dict) or not isinstance(data.get("servers"), dict):
        raise CatalogError(f"{path} is missing or not a catalog")
    return data


def unknown_servers(catalog: dict, settings: Path | None = None) -> list[str]:
    return [server for server in configured_servers(settings) if server not in catalog["servers"]]


def _listed(catalog: dict, server: str, tool: str) -> bool:
    entry = _dict(catalog["servers"].get(server))
    return any(tool in (entry.get(name) or []) for name in LISTS)


def unclassified(catalog: dict) -> dict[str, dict[str, dict]]:
    """What the gate recorded, minus what the catalog has classified since. The record is a file
    anyone could plant, and its names reach the terminal: a name outside the plain set is dropped
    and a date that is not a date is blanked, so no escape sequence is ever printed."""
    result: dict[str, dict[str, dict]] = {}
    for server, tools in _dict(_json(unclassified_path())).items():
        if not RECORDED_NAME.fullmatch(server):
            continue
        for tool, entry in _dict(tools).items():
            if not RECORDED_NAME.fullmatch(tool) or _listed(catalog, server, tool):
                continue
            count = _dict(entry).get("count")
            last = _dict(entry).get("last", "")
            result.setdefault(server, {})[tool] = {
                "count": count if isinstance(count, int) else 0,
                "last": last if isinstance(last, str) and RECORDED_DATE.fullmatch(last) else "",
            }
    return result


def report() -> dict:
    catalog = load_catalog()
    return {"missing_servers": unknown_servers(catalog), "unclassified": unclassified(catalog)}


@dataclass
class Change:
    added: list[str] = field(default_factory=list)
    already: list[str] = field(default_factory=list)
    moved: list[str] = field(default_factory=list)
    forgotten: list[str] = field(default_factory=list)


def _write_atomic(path: Path, text: str) -> None:
    """Temp file then `os.replace`; the file keeps its mode (mkstemp would make it 0600)."""
    try:
        mode = path.stat().st_mode & 0o777
    except OSError:
        mode = 0o644
    descriptor, name = tempfile.mkstemp(dir=path.parent, prefix=f".{path.name}-", suffix=".tmp")
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
            handle.write(text)
        os.chmod(name, mode)
        os.replace(name, path)
    except BaseException:
        Path(name).unlink(missing_ok=True)
        raise


def _forget(server: str, tools: list[str]) -> list[str]:
    path = unclassified_path()
    if path.parent.is_symlink() or path.is_symlink():
        return []
    data = _json(path)
    if not isinstance(data, dict) or not isinstance(data.get(server), dict):
        return []
    forgotten = [tool for tool in tools if data[server].pop(tool, None) is not None]
    if not data[server]:
        del data[server]
    if forgotten:
        _write_atomic(path, json.dumps(data, sort_keys=True))
    return forgotten


def classify(server: str, tools: list[str], target: str) -> Change:
    """Put `tools` of `server` in the `target` list (`pass` or `ask`) of the repo's catalog, take
    them out of the other list and out of the unclassified record."""
    for name in (server, *tools):
        if not TOOL_NAME.fullmatch(name):
            raise CatalogError(f"refused {name!r}: names take letters, digits, _, . and - only")
    path = catalog_path()
    catalog = load_catalog(path)
    entry = catalog["servers"].setdefault(server, {"pass": [], "ask": []})
    other = "ask" if target == "pass" else "pass"
    change = Change()
    for tool in dict.fromkeys(tools):
        if tool in entry.setdefault(other, []):
            entry[other].remove(tool)
            change.moved.append(tool)
        if tool in entry.setdefault(target, []):
            change.already.append(tool)
        else:
            entry[target].append(tool)
            change.added.append(tool)
    for name in LISTS:
        entry[name] = sorted(set(entry[name]))
    _write_atomic(path, json.dumps(catalog, indent=2, ensure_ascii=False) + "\n")
    change.forgotten = _forget(server, list(tools))
    return change
