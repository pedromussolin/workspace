import json
import os
import shutil
from pathlib import Path

import pytest

from ws import handoff
from ws.cli import main

EMPTY_ANSWER = '{"data":{"search":{"issueCount":0,"nodes":[]}}}'


@pytest.fixture
def env(tmp_path, git, monkeypatch):
    """Config, data folder, repo root and a fake `gh` that never reaches the network."""
    config = tmp_path / "config"
    config.mkdir()
    roots = tmp_path / "repos"
    roots.mkdir()
    (config / "config.toml").write_text(f'[standup]\nrepo_roots = ["{roots}"]\n', encoding="utf-8")
    root = tmp_path / "root"
    (root / "projects" / "demo").mkdir(parents=True)
    (root / "templates").mkdir()
    template = Path(handoff.__file__).resolve().parents[2] / "templates" / "handoff.md"
    shutil.copy(template, root / "templates" / "handoff.md")
    data = tmp_path / "data"
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    gh_log = tmp_path / "gh.log"
    gh = bin_dir / "gh"
    gh.write_text(f"#!/bin/sh\necho called >> {gh_log}\necho '{EMPTY_ANSWER}'\n", encoding="utf-8")
    gh.chmod(0o755)
    monkeypatch.setenv("WS_CONFIG_DIR", str(config))
    monkeypatch.setenv("WS_REPO_ROOT", str(root))
    monkeypatch.setenv("WS_DATA_DIR", str(data))
    monkeypatch.setenv("WS_CACHE_DIR", str(tmp_path / "cache"))
    monkeypatch.setenv("PATH", f"{bin_dir}{os.pathsep}{os.environ['PATH']}")

    class Env:
        pass

    result = Env()
    result.config, result.roots, result.root, result.data = config, roots, root, data
    result.gh_log = gh_log

    def repo(name: str, dirty: bool = False) -> Path:
        path = roots / name
        path.mkdir()
        git(path, "init", "-q", "-b", "main")
        (path / "a.txt").write_text("a", encoding="utf-8")
        git(path, "add", ".")
        git(path, "commit", "-q", "-m", "first")
        if dirty:
            (path / "b.txt").write_text("b", encoding="utf-8")
        return path

    result.repo = repo
    return result


def _json(capsys) -> dict:
    return json.loads(capsys.readouterr().out)


def test_collect_prints_json_without_the_clean_repos(env, capsys):
    env.repo("clean")
    env.repo("busy", dirty=True)

    assert main(["handoff", "collect"]) == 0

    result = _json(capsys)
    assert [repo["name"] for repo in result["repos"]] == ["busy"]
    assert result["clean_repos"] == 1
    assert result["prs"] == []
    assert result["fetched"] is False


def test_collect_all_lists_every_repo_and_no_prs_skips_gh(env, capsys):
    env.repo("clean")

    assert main(["handoff", "collect", "--all", "--no-prs"]) == 0

    result = _json(capsys)
    assert [repo["name"] for repo in result["repos"]] == ["clean"]
    assert not env.gh_log.exists()


def test_collect_asks_gh_by_default(env, capsys):
    assert main(["handoff", "collect"]) == 0

    capsys.readouterr()
    assert env.gh_log.exists()


def test_collect_with_a_missing_config_exits_2(env, capsys):
    (env.config / "config.toml").unlink()

    assert main(["handoff", "collect"]) == 2
    assert "config.toml" in capsys.readouterr().err


def test_collect_with_an_invalid_config_exits_2(env, capsys):
    (env.config / "config.toml").write_text("[standup]\nstale_workdays = 0\n", encoding="utf-8")

    assert main(["handoff", "collect"]) == 2
    assert "stale_workdays" in capsys.readouterr().err


def test_new_creates_the_file_and_prints_the_summary(env, capsys):
    env.repo("busy", dirty=True)

    assert main(["handoff", "new", "demo", "--topic", "meu-tema", "--date", "2026-11-03"]) == 0

    out = _json(capsys)
    path = env.data / "projects" / "demo" / "HANDOFF-20261103-meu-tema.md"
    assert out["path"] == str(path)
    assert out["repos"] == 1 and out["prs"] == 0 and out["warnings"] == []
    assert path.is_file()
    assert "| busy | main |" in path.read_text(encoding="utf-8")


def test_new_refuses_an_existing_file_with_exit_1(env, capsys):
    args = ["handoff", "new", "demo", "--topic", "x", "--date", "2026-11-03"]
    assert main(args) == 0
    capsys.readouterr()

    assert main(args) == 1
    assert "HANDOFF-20261103-x.md" in capsys.readouterr().err


def test_new_refuses_an_unknown_slug_and_a_bad_topic(env, capsys):
    assert main(["handoff", "new", "nope", "--topic", "x"]) == 1
    assert "unknown project" in capsys.readouterr().err
    assert main(["handoff", "new", "demo", "--topic", "Bad Topic"]) == 1
    assert "topic" in capsys.readouterr().err


def test_new_rejects_a_bad_date(env):
    with pytest.raises(SystemExit) as exc:
        main(["handoff", "new", "demo", "--topic", "x", "--date", "03/11/2026"])
    assert exc.value.code == 2


def test_new_with_a_missing_config_exits_2(env, capsys):
    (env.config / "config.toml").unlink()

    assert main(["handoff", "new", "demo", "--topic", "x"]) == 2


def _new(env, capsys) -> Path:
    main(["handoff", "new", "demo", "--topic", "x", "--date", "2026-11-03"])
    capsys.readouterr()
    return env.data / "projects" / "demo" / "HANDOFF-20261103-x.md"


def test_refresh_diff_prints_what_changed_and_writes_nothing(env, capsys):
    path = _new(env, capsys)
    before = path.read_bytes()
    env.repo("busy", dirty=True)

    assert main(["handoff", "refresh", str(path), "--diff"]) == 0

    assert "busy" in capsys.readouterr().out
    assert path.read_bytes() == before


def test_refresh_rewrites_the_block(env, capsys):
    path = _new(env, capsys)
    env.repo("busy", dirty=True)

    assert main(["handoff", "refresh", str(path)]) == 0

    capsys.readouterr()
    assert "| busy | main |" in path.read_text(encoding="utf-8")


def test_refresh_reports_no_changes(env, capsys):
    path = _new(env, capsys)

    assert main(["handoff", "refresh", str(path), "--diff"]) == 0
    assert capsys.readouterr().out.strip() == "no changes"


def test_refresh_a_file_without_markers_exits_1(env, tmp_path, capsys):
    path = tmp_path / "HANDOFF-20261103-x.md"
    path.write_text("# Handoff 03/11/2026: x\n", encoding="utf-8")

    assert main(["handoff", "refresh", str(path)]) == 1
    assert "markers" in capsys.readouterr().err


def test_check_exit_codes(env, capsys):
    path = _new(env, capsys)

    assert main(["handoff", "check", str(path)]) == 1
    verdict = _json(capsys)
    assert verdict["ok"] is False and verdict["problems"]

    path.write_text(
        "# Handoff 03/11/2026: x\n\n## 1. F\n\n**Próximos passos:**\n1. fazer\n\n"
        "## Estado dos repositórios\n\n<!-- ws:state:begin -->\n<!-- ws:state:end -->\n\n"
        "## Ordem sugerida ao retomar\n\n1. Ler.\n2. Fazer.\n",
        encoding="utf-8",
    )
    assert main(["handoff", "check", str(path)]) == 0
    assert _json(capsys)["ok"] is True


def test_check_reads_extra_globs_from_the_config(env, tmp_path, capsys):
    legacy = tmp_path / "legacy"
    legacy.mkdir()
    path = legacy / "HANDOFF-20261103-x.md"
    path.write_text("# Handoff 03/11/2026: x\n", encoding="utf-8")
    path.chmod(0o600)

    main(["handoff", "check", str(path)])
    assert any("outside" in p for p in _json(capsys)["problems"])

    config = env.config / "config.toml"
    config.write_text(
        config.read_text(encoding="utf-8")
        + f'[handoff]\nextra_globs = ["{legacy}/HANDOFF-*.md"]\n',
        encoding="utf-8",
    )
    main(["handoff", "check", str(path)])
    assert not any("outside" in p for p in _json(capsys)["problems"])


def test_check_a_missing_file_exits_1(env, tmp_path, capsys):
    assert main(["handoff", "check", str(tmp_path / "nope.md")]) == 1
    assert "cannot read" in capsys.readouterr().err


def test_handoff_needs_a_subcommand_and_has_help():
    with pytest.raises(SystemExit) as exc:
        main(["handoff"])
    assert exc.value.code == 2
    with pytest.raises(SystemExit) as exc:
        main(["handoff", "--help"])
    assert exc.value.code == 0


def test_check_needs_no_valid_standup_table(env, capsys):
    """`check` reads no config table that can break it: a broken [standup] does not matter."""
    path = _new(env, capsys)
    (env.config / "config.toml").write_text("[standup]\nstale_workdays = 0\n", encoding="utf-8")

    assert main(["handoff", "check", str(path)]) == 1
    assert "problems" in capsys.readouterr().out
