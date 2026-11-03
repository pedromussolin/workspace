import json
import os
import subprocess
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

from ws import handoff
from ws.userconfig import StandupConfig

NOW = datetime(2026, 11, 3, 17, 40, tzinfo=UTC)


@pytest.fixture
def world(tmp_path, git, monkeypatch):
    """A repos folder, a bare remote per repo and a workspace repo; nothing touches the network."""
    monkeypatch.setenv("WS_DATA_DIR", str(tmp_path / "data"))
    monkeypatch.setenv("WS_CACHE_DIR", str(tmp_path / "cache"))

    class World:
        roots = tmp_path / "repos"
        remotes = tmp_path / "remotes"
        workspace = tmp_path / "workspace"
        cfg = StandupConfig(repo_roots=(roots,))

        def make(self, path: Path, remote: bool = True) -> Path:
            path.mkdir(parents=True)
            git(path, "init", "-q", "-b", "main")
            (path / "a.txt").write_text("a\n", encoding="utf-8")
            git(path, "add", ".")
            git(path, "commit", "-q", "-m", "first")
            if remote:
                bare = self.remotes / f"{path.name}.git"
                bare.parent.mkdir(parents=True, exist_ok=True)
                subprocess.run(["git", "init", "-q", "--bare", "-b", "main", str(bare)], check=True)
                git(path, "remote", "add", "origin", str(bare))
                git(path, "push", "-q", "-u", "origin", "main")
                git(path, "remote", "set-head", "origin", "main")
            return path

        def repo(self, name: str, remote: bool = True) -> Path:
            return self.make(self.roots / name, remote)

        def commit(self, repo: Path, name: str = "b.txt") -> None:
            (repo / name).write_text(name, encoding="utf-8")
            git(repo, "add", name)
            git(repo, "commit", "-q", "-m", f"add {name}")

        def collect(self, **kwargs) -> dict:
            kwargs.setdefault("prs", False)
            kwargs.setdefault("now", NOW)
            return handoff.collect(self.cfg, self.workspace, **kwargs)

        def only(self, name: str, **kwargs) -> dict:
            return next(r for r in self.collect(**kwargs)["repos"] if r["name"] == name)

    world = World()
    world.roots.mkdir()
    world.make(world.workspace)
    return world


def _fake_bin(tmp_path: Path, monkeypatch, name: str, body: str) -> Path:
    folder = tmp_path / "fake-bin"
    folder.mkdir(exist_ok=True)
    script = folder / name
    script.write_text(f"#!/bin/sh\n{body}\n", encoding="utf-8")
    script.chmod(0o755)
    monkeypatch.setenv("PATH", f"{folder}{os.pathsep}{os.environ['PATH']}")
    return script


def test_collect_reports_branch_upstream_ahead_behind(world, git):
    repo = world.repo("alpha")
    world.commit(repo)
    other = world.remotes.parent / "other"
    subprocess.run(["git", "clone", "-q", str(world.remotes / "alpha.git"), str(other)], check=True)
    world.commit(other, "c.txt")
    git(other, "push", "-q", "origin", "main")
    git(repo, "fetch", "-q", "origin")

    found = world.only("alpha")

    assert found["branch"] == "main"
    assert found["default_branch"] == "main"
    assert found["upstream"] == "origin/main"
    assert (found["ahead"], found["behind"], found["gone"]) == (1, 1, False)
    assert found["uncommitted"] == {"count": 0, "paths": [], "more": 0}
    assert found["stashes"] == 0 and found["worktrees"] == []


def test_collect_detached_head(world, git):
    repo = world.repo("alpha")
    git(repo, "checkout", "-q", "--detach")

    found = world.only("alpha")

    assert found["branch"] is None
    assert found["detached"] == git(repo, "rev-parse", "--short", "HEAD").stdout.strip()


def test_collect_gone_upstream(world, git):
    repo = world.repo("alpha")
    git(repo, "checkout", "-q", "-b", "feature/TS-1-x")
    git(repo, "push", "-q", "-u", "origin", "feature/TS-1-x")
    git(repo, "push", "-q", "origin", "--delete", "feature/TS-1-x")
    git(repo, "fetch", "-q", "--prune", "origin")

    found = world.only("alpha")

    assert found["branch"] == "feature/TS-1-x"
    assert found["gone"] is True
    assert found["upstream"] == "origin/feature/TS-1-x"


def test_collect_uncommitted_paths_capped_at_10_with_more(world):
    repo = world.repo("alpha")
    for index in range(13):
        (repo / f"f{index:02d}.txt").write_text("x", encoding="utf-8")

    found = world.only("alpha")

    assert found["uncommitted"]["count"] == 13
    assert found["uncommitted"]["paths"] == [f"f{index:02d}.txt" for index in range(10)]
    assert found["uncommitted"]["more"] == 3


def test_collect_uncommitted_counts_a_rename_once(world, git):
    repo = world.repo("alpha")
    git(repo, "mv", "a.txt", "renamed.txt")

    found = world.only("alpha")

    assert found["uncommitted"]["count"] == 1
    assert found["uncommitted"]["paths"] == ["renamed.txt"]


def test_collect_worktrees_with_their_state(world, git, tmp_path):
    repo = world.repo("alpha")
    tree = tmp_path / "trees" / "wt1"
    git(repo, "worktree", "add", "-q", "-b", "feature/TS-2-y", str(tree))
    world.commit(tree)
    (tree / "dirty.txt").write_text("x", encoding="utf-8")

    found = world.only("alpha")

    [entry] = found["worktrees"]
    assert entry["path"] == str(tree)
    assert entry["branch"] == "feature/TS-2-y"
    assert entry["head"] == git(tree, "rev-parse", "--short", "HEAD").stdout.strip()
    assert entry["uncommitted"] == 1
    assert (entry["ahead"], entry["behind"]) == (1, 0)
    assert entry["locked"] is False and entry["prunable"] is False


def test_collect_prunable_worktree(world, git, tmp_path):
    repo = world.repo("alpha")
    tree = tmp_path / "trees" / "gone"
    git(repo, "worktree", "add", "-q", "-b", "feature/TS-3-z", str(tree))
    subprocess.run(["rm", "-rf", str(tree)], check=True)

    [entry] = world.only("alpha")["worktrees"]

    assert entry["prunable"] is True
    assert entry["uncommitted"] is None


def test_collect_stash_count(world, git):
    repo = world.repo("alpha")
    for name in ("one", "two"):
        (repo / "a.txt").write_text(name, encoding="utf-8")
        git(repo, "stash", "push", "-q", "-m", name)

    assert world.only("alpha")["stashes"] == 2


def test_collect_local_only_branches_of_last_14_days(world, git, monkeypatch):
    repo = world.repo("alpha")
    git(repo, "checkout", "-q", "-b", "feature/TS-4-new")
    world.commit(repo, "n.txt")
    git(repo, "checkout", "-q", "-b", "feature/TS-5-old", "main")
    monkeypatch.setenv("GIT_COMMITTER_DATE", "2020-01-01T10:00:00+00:00")
    world.commit(repo, "o.txt")
    monkeypatch.delenv("GIT_COMMITTER_DATE")
    git(repo, "checkout", "-q", "-b", "feature/TS-6-merged", "main")
    git(repo, "checkout", "-q", "main")

    found = world.only("alpha")

    assert [branch["name"] for branch in found["local_branches"]] == ["feature/TS-4-new"]
    [branch] = found["local_branches"]
    assert branch["ahead"] == 1 and branch["upstream"] is None
    assert len(branch["last_commit"]) == 10 and branch["last_commit"][4] == "-"


def test_collect_clean_repos_counted_not_listed(world):
    world.repo("alpha")
    world.repo("beta")
    dirty = world.repo("gamma")
    (dirty / "x.txt").write_text("x", encoding="utf-8")

    result = world.collect()

    assert [repo["name"] for repo in result["repos"]] == ["gamma"]
    assert result["clean_repos"] == 3
    assert result["fetched"] is False


def test_collect_all_lists_clean_repos(world):
    world.repo("alpha")
    world.repo("beta")

    result = world.collect(include_clean=True)

    assert {repo["name"] for repo in result["repos"]} == {"alpha", "beta", "workspace"}
    assert result["clean_repos"] == 0


def test_collect_includes_the_workspace_repo(world):
    (world.workspace / "note.txt").write_text("x", encoding="utf-8")

    result = world.collect()

    assert [repo["name"] for repo in result["repos"]] == ["workspace"]


def test_collect_git_timeout_becomes_warning(world, tmp_path, monkeypatch):
    world.repo("alpha")
    _fake_bin(tmp_path, monkeypatch, "git", "sleep 5")
    monkeypatch.setattr(handoff, "GIT_TIMEOUT", 0.2)

    result = world.collect()

    assert result["repos"] == []
    assert any("alpha" in warning and "timed out" in warning for warning in result["warnings"])


def test_collect_sets_git_optional_locks(world, tmp_path, monkeypatch):
    world.repo("alpha")
    real = subprocess.run(["which", "git"], capture_output=True, text=True).stdout.strip()
    log = tmp_path / "locks.log"
    _fake_bin(
        tmp_path,
        monkeypatch,
        "git",
        f'echo "$GIT_OPTIONAL_LOCKS" >> {log}\nexec {real} "$@"',
    )

    world.collect()

    values = set(log.read_text(encoding="utf-8").split())
    assert values == {"0"}


GRAPHQL = {
    "data": {
        "search": {
            "issueCount": 1,
            "nodes": [
                {
                    "number": 12,
                    "title": "Fix x",
                    "url": "https://example.test/o/r/pull/12",
                    "baseRefName": "master",
                    "headRefName": "release/20261103",
                    "isDraft": False,
                    "reviewDecision": "APPROVED",
                    "updatedAt": "2026-11-03T10:00:00Z",
                    "repository": {"name": "alpha"},
                }
            ],
        }
    }
}


def test_collect_parses_open_prs(world, tmp_path, monkeypatch):
    payload = tmp_path / "answer.json"
    payload.write_text(json.dumps(GRAPHQL), encoding="utf-8")
    gh = _fake_bin(tmp_path, monkeypatch, "gh", f"cat {payload}")

    result = world.collect(prs=True, gh=str(gh))

    assert result["prs"] == [
        {
            "repo": "alpha",
            "number": 12,
            "title": "Fix x",
            "url": "https://example.test/o/r/pull/12",
            "base": "master",
            "head": "release/20261103",
            "draft": False,
            "review": "APPROVED",
            "updated": "2026-11-03T10:00:00Z",
        }
    ]
    assert result["warnings"] == []


def test_collect_gh_failure_is_a_warning(world, tmp_path, monkeypatch):
    gh = _fake_bin(tmp_path, monkeypatch, "gh", "echo 'not logged in' >&2\nexit 1")

    result = world.collect(prs=True, gh=str(gh))

    assert result["prs"] == []
    assert any(
        warning.startswith("gh:") and "not logged in" in warning for warning in result["warnings"]
    )


def test_collect_no_prs_never_calls_gh(world, tmp_path, monkeypatch):
    log = tmp_path / "gh.log"
    gh = _fake_bin(tmp_path, monkeypatch, "gh", f"echo called >> {log}")

    world.collect(prs=False, gh=str(gh))

    assert not log.exists()


def test_collect_counts_recent_hook_errors(world, tmp_path):
    log = tmp_path / "cache" / "hooks" / "errors.log"
    log.parent.mkdir(parents=True)
    recent = (NOW - timedelta(days=1)).isoformat()
    old = (NOW - timedelta(days=9)).isoformat()
    log.write_text(
        f"{recent} context_watch KeyError\n"
        f"{recent} context_watch no-usage\n"
        f"{recent} handoff_pointer OSError\n"
        f"{old} context_watch KeyError\n"
        "garbage line\n",
        encoding="utf-8",
    )

    warnings = world.collect()["warnings"]

    [warning] = [w for w in warnings if w.startswith("hooks:")]
    assert "3 failure" in warning
    assert "context_watch 2" in warning and "handoff_pointer 1" in warning


def test_collect_lists_the_newest_handoffs(world, tmp_path):
    folder = tmp_path / "data" / "projects" / "demo"
    folder.mkdir(parents=True)
    (folder / "HANDOFF-20261103-x.md").write_text("# Handoff 03/11/2026: tema\n", encoding="utf-8")

    [entry] = world.collect()["handoffs"]

    assert entry["project"] == "demo"
    assert entry["title"] == "Handoff 03/11/2026: tema"
    assert entry["closed"] is False
    assert entry["path"].endswith("projects/demo/HANDOFF-20261103-x.md")


def _handoff_file(folder: Path, name: str, text: str, age_days: float = 0) -> Path:
    folder.mkdir(parents=True, exist_ok=True)
    path = folder / name
    path.write_text(text, encoding="utf-8")
    stamp = (NOW - timedelta(days=age_days)).timestamp()
    os.utime(path, (stamp, stamp))
    return path


def test_find_handoffs_newest_first_within_age(tmp_path):
    data = tmp_path / "data"
    folder = data / "projects" / "demo"
    _handoff_file(folder, "HANDOFF-20261101-a.md", "# Handoff 01/11/2026: a\n", age_days=2)
    _handoff_file(folder, "HANDOFF-20261103-b.md", "# Handoff 03/11/2026: b\n", age_days=0.1)
    _handoff_file(folder, "HANDOFF-20261020-c.md", "# Handoff 20/10/2026: c\n", age_days=14)
    legacy = tmp_path / "legacy"
    _handoff_file(legacy, "HANDOFF-20261102-d.md", "# Handoff 02/11/2026: d\n", age_days=1)

    found = handoff.find_handoffs(
        data, [str(legacy / "HANDOFF-*.md")], limit=3, max_age_days=7, now=NOW
    )

    assert [Path(item["path"]).name for item in found] == [
        "HANDOFF-20261103-b.md",
        "HANDOFF-20261102-d.md",
        "HANDOFF-20261101-a.md",
    ]
    assert found[0]["title"] == "Handoff 03/11/2026: b"
    limited = handoff.find_handoffs(data, [], limit=1, max_age_days=7, now=NOW)
    assert len(limited) == 1


def test_find_handoffs_skips_closed(tmp_path):
    folder = tmp_path / "data" / "projects" / "demo"
    _handoff_file(folder, "HANDOFF-20261103-a.md", "# Handoff 03/11/2026: a\nStatus: encerrado\n")
    _handoff_file(folder, "HANDOFF-20261103-b.md", "# Handoff 03/11/2026: b\n")

    found = handoff.find_handoffs(tmp_path / "data", [], limit=3, max_age_days=7, now=NOW)
    everything = handoff.find_handoffs(
        tmp_path / "data", [], limit=3, max_age_days=None, now=NOW, include_closed=True
    )

    assert [Path(item["path"]).name for item in found] == ["HANDOFF-20261103-b.md"]
    assert {item["closed"] for item in everything} == {True, False}
