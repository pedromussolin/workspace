import json
from pathlib import Path

import pytest

from ws import gatecatalog
from ws.cli import main

CATALOG = {
    "version": 1,
    "servers": {
        "plugin_alpha_alpha": {"pass": ["get_one", "list_all"], "ask": ["write_one"]},
        "claude_ai_Some_Service": {"pass": ["read"]},
    },
    "notes": {"plugin_alpha_alpha__write_one": "Not a pass: writes."},
}


def write_json(path: Path, data: object) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data), encoding="utf-8")
    return path


def add_plugin(home: Path, key: str, files: dict[str, object], enabled: bool = True) -> Path:
    name, _, market = key.partition("@")
    install = home / "plugins" / "cache" / market / name
    for rel, data in files.items():
        write_json(install / rel, data)
    installed = home / "plugins" / "installed_plugins.json"
    current = json.loads(installed.read_text()) if installed.exists() else {"plugins": {}}
    current["plugins"][key] = [{"scope": "user", "installPath": str(install)}]
    write_json(installed, current)
    settings = home / "settings.json"
    data = json.loads(settings.read_text()) if settings.exists() else {"enabledPlugins": {}}
    data["enabledPlugins"][key] = enabled
    write_json(settings, data)
    return install


@pytest.fixture
def home(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    folder = tmp_path / "claude"
    folder.mkdir()
    repo = tmp_path / "repo"
    write_json(repo / "hooks" / "gate" / "catalog.json", CATALOG)
    monkeypatch.setenv("WS_REPO_ROOT", str(repo))
    monkeypatch.setenv("WS_CLAUDE_SETTINGS", str(folder / "settings.json"))
    monkeypatch.setenv("WS_CLAUDE_JSON", str(folder / "claude.json"))
    monkeypatch.setenv("WS_CLAUDE_PLUGINS_DIR", str(folder / "plugins"))
    return folder


def catalog_file() -> Path:
    return gatecatalog.catalog_path()


def record(data: dict) -> None:
    write_json(gatecatalog.unclassified_path(), data)


def test_no_configuration_means_no_servers(home):
    assert gatecatalog.configured_servers() == []


def test_a_plugin_server_from_mcp_json_top_level(home):
    add_plugin(home, "higgs-hub@market", {".mcp.json": {"higgs-hub": {"type": "http"}}})

    assert gatecatalog.configured_servers() == ["plugin_higgs-hub_higgs-hub"]


def test_a_plugin_server_from_mcp_json_under_mcp_servers(home):
    add_plugin(home, "github@market", {".mcp.json": {"mcpServers": {"github": {"url": "u"}}}})

    assert gatecatalog.configured_servers() == ["plugin_github_github"]


def test_plugin_servers_from_the_manifest_object_and_from_a_relative_file(home):
    add_plugin(
        home,
        "inline@market",
        {".claude-plugin/plugin.json": {"mcpServers": {"one": {"command": "x"}}}},
    )
    add_plugin(
        home,
        "pointed@market",
        {
            ".claude-plugin/plugin.json": {"mcpServers": "./servers.json"},
            "servers.json": {"mcpServers": {"two": {"command": "y"}}},
        },
    )

    assert gatecatalog.configured_servers() == ["plugin_inline_one", "plugin_pointed_two"]


def test_a_manifest_path_that_leaves_the_plugin_folder_is_ignored(home):
    outside = write_json(home / "outside.json", {"leak": {"command": "x"}})
    add_plugin(
        home,
        "sneaky@market",
        {".claude-plugin/plugin.json": {"mcpServers": f"../../../../{outside.name}"}},
    )

    assert gatecatalog.configured_servers() == []


def test_a_disabled_or_not_installed_plugin_is_skipped(home):
    add_plugin(home, "off@market", {".mcp.json": {"off": {"url": "u"}}}, enabled=False)
    settings = home / "settings.json"
    data = json.loads(settings.read_text())
    data["enabledPlugins"]["ghost@market"] = True
    write_json(settings, data)

    assert gatecatalog.configured_servers() == []


def test_user_local_and_connector_servers_from_claude_json(home):
    write_json(
        home / "claude.json",
        {
            "mcpServers": {"github": {"type": "http", "headers": {"x": "value-never-shown"}}},
            "projects": {"/some/project": {"mcpServers": {"local-one": {"command": "z"}}}},
            "claudeAiMcpEverConnected": [
                "claude.ai Atlassian MCP",
                "claude.ai Microsoft 365",
                "claude.ai Claude Docs",
            ],
        },
    )

    assert gatecatalog.configured_servers() == [
        "claude_ai_Atlassian_MCP",
        "claude_ai_Claude_Docs",
        "claude_ai_Microsoft_365",
        "github",
        "local-one",
    ]


@pytest.mark.parametrize("content", ["not json", "[1]", '{"mcpServers": 3, "projects": [1]}'])
def test_unreadable_files_are_skipped_silently(home, content):
    (home / "claude.json").write_text(content, encoding="utf-8")
    (home / "settings.json").write_text(content, encoding="utf-8")

    assert gatecatalog.configured_servers() == []


def test_unknown_servers_are_the_configured_ones_the_catalog_lacks(home):
    write_json(
        home / "claude.json",
        {"mcpServers": {"plugin_alpha_alpha": {}, "brand-new": {}}},
    )

    assert gatecatalog.unknown_servers(gatecatalog.load_catalog()) == ["brand-new"]


def test_a_missing_catalog_is_an_error(home, monkeypatch, tmp_path):
    monkeypatch.setenv("WS_REPO_ROOT", str(tmp_path / "nowhere"))

    with pytest.raises(gatecatalog.CatalogError):
        gatecatalog.load_catalog()


def test_unclassified_hides_what_the_catalog_now_knows(home):
    record(
        {
            "plugin_alpha_alpha": {
                "get_one": {"count": 4, "last": "2026-10-01"},
                "fresh": {"count": 2, "last": "2026-10-02"},
            },
            "other": {"x": {"count": 1, "last": "2026-10-03"}},
        }
    )

    found = gatecatalog.unclassified(gatecatalog.load_catalog())

    assert found == {
        "plugin_alpha_alpha": {"fresh": {"count": 2, "last": "2026-10-02"}},
        "other": {"x": {"count": 1, "last": "2026-10-03"}},
    }


def test_classify_pass_adds_sorted_and_creates_the_server(home):
    change = gatecatalog.classify("plugin_alpha_alpha", ["b_tool", "a_tool"], "pass")
    gatecatalog.classify("brand-new", ["x"], "ask")

    assert change.added == ["b_tool", "a_tool"]
    data = json.loads(catalog_file().read_text(encoding="utf-8"))
    assert data["servers"]["plugin_alpha_alpha"]["pass"] == [
        "a_tool",
        "b_tool",
        "get_one",
        "list_all",
    ]
    assert data["servers"]["brand-new"] == {"pass": [], "ask": ["x"]}
    assert data["notes"] == CATALOG["notes"]


def test_classify_moves_a_tool_from_the_other_list(home):
    change = gatecatalog.classify("plugin_alpha_alpha", ["write_one", "get_one"], "ask")

    assert change.moved == ["get_one"]
    assert change.already == ["write_one"]
    entry = json.loads(catalog_file().read_text(encoding="utf-8"))["servers"]["plugin_alpha_alpha"]
    assert entry == {"pass": ["list_all"], "ask": ["get_one", "write_one"]}


def test_classify_fills_the_ask_list_of_an_entry_that_has_none(home):
    gatecatalog.classify("claude_ai_Some_Service", ["send"], "ask")

    entry = json.loads(catalog_file().read_text(encoding="utf-8"))["servers"]
    assert entry["claude_ai_Some_Service"] == {"pass": ["read"], "ask": ["send"]}


def test_classify_formatting_is_stable_and_keeps_the_file_mode(home):
    catalog_file().chmod(0o644)
    gatecatalog.classify("plugin_alpha_alpha", ["z"], "pass")
    first = catalog_file().read_text(encoding="utf-8")
    gatecatalog.classify("plugin_alpha_alpha", ["z"], "pass")

    assert catalog_file().read_text(encoding="utf-8") == first
    assert first.endswith("}\n")
    assert first == json.dumps(json.loads(first), indent=2, ensure_ascii=False) + "\n"
    assert oct(catalog_file().stat().st_mode & 0o777) == "0o644"
    assert [p.name for p in catalog_file().parent.iterdir()] == ["catalog.json"]


def test_classify_forgets_the_tools_in_the_unclassified_record(home):
    record(
        {
            "srv": {"a": {"count": 1, "last": "d"}, "b": {"count": 1, "last": "d"}},
            "keep": {"a": {"count": 1, "last": "d"}},
        }
    )

    change = gatecatalog.classify("srv", ["a", "never_seen"], "pass")

    assert change.forgotten == ["a"]
    left = json.loads(gatecatalog.unclassified_path().read_text(encoding="utf-8"))
    assert left == {
        "srv": {"b": {"count": 1, "last": "d"}},
        "keep": {"a": {"count": 1, "last": "d"}},
    }


def test_classify_drops_a_server_whose_record_became_empty(home):
    record({"srv": {"a": {"count": 1, "last": "d"}}})

    gatecatalog.classify("srv", ["a"], "ask")

    assert json.loads(gatecatalog.unclassified_path().read_text(encoding="utf-8")) == {}


@pytest.mark.parametrize("bad", ["", "has space", "semi;colon", "slash/x", "ação", "a\nb"])
def test_classify_refuses_a_name_that_is_not_plain(home, bad):
    before = catalog_file().read_bytes()

    with pytest.raises(gatecatalog.CatalogError):
        gatecatalog.classify("srv", ["ok", bad], "pass")
    with pytest.raises(gatecatalog.CatalogError):
        gatecatalog.classify(bad, ["ok"], "pass")

    assert catalog_file().read_bytes() == before


def test_cli_report_text(home, capsys):
    write_json(home / "claude.json", {"mcpServers": {"brand-new": {}}})
    record({"plugin_alpha_alpha": {"fresh": {"count": 3, "last": "2026-10-29"}}})

    assert main(["gate", "catalog"]) == 0

    out = capsys.readouterr().out
    assert "brand-new" in out
    assert "fresh  (3 asks, last 2026-10-29)" in out
    assert "ws gate catalog pass SERVER TOOL..." in out


def test_cli_report_json(home, capsys):
    write_json(home / "claude.json", {"mcpServers": {"brand-new": {}}})
    record({"srv": {"t": {"count": 1, "last": "2026-10-29"}}})

    assert main(["gate", "catalog", "--json"]) == 0

    assert json.loads(capsys.readouterr().out) == {
        "missing_servers": ["brand-new"],
        "unclassified": {"srv": {"t": {"count": 1, "last": "2026-10-29"}}},
    }


def test_cli_report_with_nothing_to_classify(home, capsys):
    assert main(["gate", "catalog"]) == 0
    assert "Nothing to classify" in capsys.readouterr().out


def test_cli_never_prints_config_values(home, capsys):
    write_json(
        home / "claude.json",
        {"mcpServers": {"brand-new": {"headers": {"Authorization": "Bearer abc123xyz"}}}},
    )

    main(["gate", "catalog"])
    main(["gate", "catalog", "--json"])

    assert "abc123xyz" not in capsys.readouterr().out


def test_cli_pass_and_ask_print_what_changed(home, capsys):
    record({"srv": {"t": {"count": 1, "last": "d"}}})

    assert main(["gate", "catalog", "pass", "srv", "t", "u"]) == 0
    out = capsys.readouterr().out
    assert "added to srv: pass: t, u" in out
    assert "removed from the unclassified record: t" in out
    assert "commit the file and run ws setup in your terminal to update the protected copy" in out

    assert main(["gate", "catalog", "ask", "srv", "u"]) == 0
    assert "removed from srv: pass: u" in capsys.readouterr().out


def test_cli_refuses_a_bad_name_with_exit_1(home, capsys):
    before = catalog_file().read_bytes()

    assert main(["gate", "catalog", "pass", "srv", "bad name"]) == 1

    assert "refused" in capsys.readouterr().err
    assert catalog_file().read_bytes() == before


def test_cli_without_a_catalog_exits_1(home, monkeypatch, tmp_path, capsys):
    monkeypatch.setenv("WS_REPO_ROOT", str(tmp_path / "nowhere"))

    assert main(["gate", "catalog"]) == 1
    assert "not a catalog" in capsys.readouterr().err
