import json
import os
import subprocess
import sys
from collections.abc import Callable
from datetime import date
from pathlib import Path

import pytest

from ws.cli import main
from ws.standup import _section, collect, keys_in
from ws.userconfig import StandupConfig

Git = Callable[..., subprocess.CompletedProcess[str]]

MONDAY = date(2026, 10, 26)
GH_ANSWER = {
    "data": {
        "search": {
            "issueCount": 2,
            "nodes": [
                {
                    "number": 12,
                    "title": "feat(TS-101): tela de exemplo",
                    "state": "OPEN",
                    "mergedAt": None,
                    "updatedAt": "2026-10-26T09:30:00Z",
                    "headRefName": "feature/TS-101-tela",
                    "url": "https://github.com/example/app/pull/12",
                    "repository": {"name": "app"},
                },
                {
                    "number": 7,
                    "title": "chore(TS-101, TS-102): ajuste",
                    "state": "MERGED",
                    "mergedAt": "2026-10-26T17:14:40Z",
                    "updatedAt": "2026-10-26T17:14:41Z",
                    "headRefName": "chore/TS-102-ajuste",
                    "url": "https://github.com/example/api/pull/7",
                    "repository": {"name": "api"},
                },
            ],
        }
    }
}

FAKE_GH = """\
#!{python}
import os, pathlib, sys

pathlib.Path(os.environ["FAKE_GH_LOG"]).write_text("\\n".join(sys.argv[1:]), encoding="utf-8")
if os.environ.get("FAKE_GH_FAIL"):
    print(os.environ["FAKE_GH_FAIL"], file=sys.stderr)
    print("second line", file=sys.stderr)
    sys.exit(1)
sys.stdout.buffer.write(pathlib.Path(os.environ["FAKE_GH_ANSWER"]).read_bytes())
"""


class FakeGh:
    def __init__(self, folder: Path, monkeypatch: pytest.MonkeyPatch):
        self.log = folder / "args.txt"
        self.answer = folder / "answer.json"
        self.answer.write_text(json.dumps(GH_ANSWER), encoding="utf-8")
        script = folder / "gh"
        script.write_text(FAKE_GH.format(python=sys.executable), encoding="utf-8")
        script.chmod(0o755)
        monkeypatch.setenv("FAKE_GH_LOG", str(self.log))
        monkeypatch.setenv("FAKE_GH_ANSWER", str(self.answer))
        monkeypatch.setenv("PATH", f"{folder}{os.pathsep}{os.environ['PATH']}")

    def args(self) -> list[str]:
        return self.log.read_text(encoding="utf-8").splitlines()


@pytest.fixture
def fake_gh(tmp_path_factory: pytest.TempPathFactory, monkeypatch: pytest.MonkeyPatch) -> FakeGh:
    return FakeGh(tmp_path_factory.mktemp("fake-gh"), monkeypatch)


@pytest.fixture
def home(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    folder = tmp_path / "home"
    folder.mkdir()
    monkeypatch.setenv("HOME", str(folder))
    return folder


@pytest.fixture
def roots(tmp_path: Path) -> Path:
    folder = tmp_path / "repos"
    folder.mkdir()
    return folder


@pytest.fixture
def workspace(tmp_path: Path) -> Path:
    folder = tmp_path / "workspace"
    (folder / "projects").mkdir(parents=True)
    return folder


@pytest.fixture
def make_repo(roots: Path, git: Git) -> Callable[..., Path]:
    def make(name: str, email: str | None = "dev@example.com") -> Path:
        path = roots / name
        path.mkdir()
        git(path, "init", "-q")
        if email:
            git(path, "config", "user.email", email)
        return path

    return make


@pytest.fixture
def commit(git: Git, monkeypatch: pytest.MonkeyPatch) -> Callable[..., None]:
    def make(repo: Path, subject: str, day: str, email: str = "dev@example.com") -> None:
        stamp = f"{day}T12:00:00"
        monkeypatch.setenv("GIT_AUTHOR_DATE", stamp)
        monkeypatch.setenv("GIT_COMMITTER_DATE", stamp)
        git(repo, "commit", "-q", "--allow-empty", "-m", subject, f"--author=Dev <{email}>")

    return make


def _collect(roots: Path, workspace: Path, today: date = MONDAY, stale: int = 3) -> dict:
    return collect(StandupConfig(repo_roots=(roots,), stale_workdays=stale), today, workspace)


def test_keys_in_keeps_order_and_drops_repeats():
    assert keys_in("feat(TS-101, TS-102): x TS-101 and ab-3") == ["TS-101", "TS-102"]
    assert keys_in("no key here") == []


def test_window_on_monday_starts_friday(roots, workspace, fake_gh, home):
    result = _collect(roots, workspace)
    assert result["window"] == {"since": "2026-10-23", "until": "2026-10-26", "kind": "daily"}
    assert "updated:>=2026-10-21" in "\n".join(fake_gh.args())


def test_author_is_each_repos_git_email(roots, workspace, fake_gh, home, make_repo, commit):
    first = make_repo("first", "one@example.com")
    second = make_repo("second", "two@example.com")
    nameless = make_repo("nameless", None)
    commit(first, "feat(TS-1): mine in first", "2026-10-26", "one@example.com")
    commit(first, "feat(TS-2): from another author", "2026-10-26", "other@example.com")
    commit(second, "feat(TS-3): mine in second", "2026-10-26", "two@example.com")
    commit(second, "feat(TS-4): first author's address", "2026-10-26", "one@example.com")
    commit(nameless, "feat(TS-5): nobody", "2026-10-26", "one@example.com")
    result = _collect(roots, workspace)
    assert [(c["repo"], c["subject"]) for c in result["commits"]] == [
        ("first", "feat(TS-1): mine in first"),
        ("second", "feat(TS-3): mine in second"),
    ]
    assert result["commits"][0]["keys"] == ["TS-1"]
    assert result["commits"][0]["date"] == "2026-10-26"
    assert len(result["commits"][0]["sha"]) == 40
    assert any("nameless" in warning and "user.email" in warning for warning in result["warnings"])


def test_commit_just_after_midnight_of_the_first_day_is_kept(
    roots, workspace, fake_gh, home, make_repo, commit, git, monkeypatch
):
    repo = make_repo("app")
    monkeypatch.setenv("GIT_AUTHOR_DATE", "2026-10-23T00:30:00")
    monkeypatch.setenv("GIT_COMMITTER_DATE", "2026-10-23T00:30:00")
    git(
        repo,
        "commit",
        "-q",
        "--allow-empty",
        "-m",
        "feat(TS-1): early",
        "--author=Dev <dev@example.com>",
    )
    result = _collect(roots, workspace)
    assert [c["subject"] for c in result["commits"]] == ["feat(TS-1): early"]
    assert result["last_activity"] == {"TS-1": "2026-10-23"}
    assert _collect(roots, workspace, stale=1)["commits"][0]["subject"] == "feat(TS-1): early"


def test_commit_before_the_window_is_left_out(roots, workspace, fake_gh, home, make_repo, commit):
    repo = make_repo("app")
    commit(repo, "feat(TS-1): old", "2026-10-22")
    commit(repo, "feat(TS-2): in the window", "2026-10-23")
    result = _collect(roots, workspace)
    assert [c["subject"] for c in result["commits"]] == ["feat(TS-2): in the window"]


def test_keys_from_subject_and_branch(roots, workspace, fake_gh, home, make_repo, commit, git):
    repo = make_repo("app")
    commit(repo, "feat(TS-101): tela", "2026-10-26")
    git(repo, "branch", "feature/TS-101-tela")
    git(repo, "branch", "no-key-here")
    result = _collect(roots, workspace)
    assert result["commits"][0]["keys"] == ["TS-101"]
    assert result["branches"] == [
        {"repo": "app", "name": "feature/TS-101-tela", "keys": ["TS-101"]}
    ]
    assert [(pr["repo"], pr["keys"]) for pr in result["prs"]] == [
        ("app", ["TS-101"]),
        ("api", ["TS-101", "TS-102"]),
    ]


def test_several_keys_in_one_title(roots, workspace, fake_gh, home, make_repo, commit):
    repo = make_repo("app")
    commit(repo, "chore(TS-101, TS-102): x", "2026-10-26")
    result = _collect(roots, workspace)
    assert result["commits"][0]["keys"] == ["TS-101", "TS-102"]
    assert result["last_activity"] == {"TS-101": "2026-10-26", "TS-102": "2026-10-26"}


def test_prs_come_from_one_search(roots, workspace, fake_gh, home):
    result = _collect(roots, workspace)
    assert result["prs"][1] == {
        "repo": "api",
        "number": 7,
        "title": "chore(TS-101, TS-102): ajuste",
        "state": "merged",
        "merged_at": "2026-10-26T17:14:40Z",
        "updated_at": "2026-10-26T17:14:41Z",
        "url": "https://github.com/example/api/pull/7",
        "keys": ["TS-101", "TS-102"],
    }
    assert result["prs"][0]["state"] == "open"
    assert result["prs"][0]["merged_at"] is None
    args = fake_gh.args()
    assert args[:2] == ["api", "graphql"]
    assert "q=is:pr author:@me updated:>=2026-10-21" in args


@pytest.mark.parametrize(
    "answer",
    [
        {"data": {"search": None}},
        {"data": {"search": {"nodes": []}}},
        {"data": {"search": {"issueCount": 1, "nodes": [{"number": 1}]}}},
        {"errors": ["boom"]},
        "not json at all",
    ],
)
def test_malformed_gh_answer_is_one_warning(roots, workspace, fake_gh, home, answer):
    fake_gh.answer.write_text(
        answer if isinstance(answer, str) else json.dumps(answer), encoding="utf-8"
    )
    result = _collect(roots, workspace)
    assert result["prs"] == []
    assert sum(w.startswith("gh: PRs left out") for w in result["warnings"]) == 1


def test_more_than_a_hundred_prs_is_a_warning(roots, workspace, fake_gh, home):
    fake_gh.answer.write_text(
        json.dumps({"data": {"search": {"issueCount": 130, "nodes": []}}}), encoding="utf-8"
    )
    assert any("100" in warning for warning in _collect(roots, workspace)["warnings"])


def test_repos_found_under_roots_and_missing_root_is_a_warning(
    tmp_path, roots, workspace, fake_gh, home, make_repo, commit, git
):
    commit(make_repo("zeta"), "feat(TS-1): z", "2026-10-26")
    commit(make_repo("alpha"), "feat(TS-2): a", "2026-10-26")
    (roots / "plain-folder").mkdir()
    (roots / "a-file").write_text("x", encoding="utf-8")
    hidden = roots / ".hidden"
    hidden.mkdir()
    git(hidden, "init", "-q")
    git(hidden, "config", "user.email", "dev@example.com")
    commit(hidden, "feat(TS-3): hidden", "2026-10-26")
    git(roots / "alpha", "worktree", "add", "-q", str(roots / "linked"))
    missing = tmp_path / "no-such-root"
    cfg = StandupConfig(repo_roots=(roots, missing))
    result = collect(cfg, MONDAY, workspace)
    assert [c["repo"] for c in result["commits"]] == ["alpha", "zeta"]
    assert any(str(missing) in warning for warning in result["warnings"])


def test_the_workspace_repo_is_skipped(roots, fake_gh, home, git, commit):
    own = roots / "workspace"
    (own / "projects").mkdir(parents=True)
    git(own, "init", "-q")
    git(own, "config", "user.email", "dev@example.com")
    commit(own, "feat(TS-1): planning", "2026-10-26")
    assert _collect(roots, own)["commits"] == []


def test_gh_failure_is_one_warning(roots, workspace, fake_gh, home, monkeypatch):
    monkeypatch.setenv("FAKE_GH_FAIL", "gh auth login required")
    result = _collect(roots, workspace)
    assert result["prs"] == []
    assert [w for w in result["warnings"] if w.startswith("gh:")] == [
        "gh: PRs left out (gh auth login required)"
    ]


def test_gh_not_installed_is_one_warning(roots, workspace, home, monkeypatch):
    monkeypatch.setenv("PATH", str(roots))
    result = collect(StandupConfig(repo_roots=(roots,)), MONDAY, workspace)
    assert result["prs"] == []
    assert sum(w.startswith("gh:") for w in result["warnings"]) == 1


def test_next_steps_from_continue_and_warning_without_section(roots, workspace, fake_gh, home):
    first = workspace / "projects" / "alpha"
    first.mkdir()
    (first / "CONTINUE.md").write_text(
        "# Continuar\n\n## Onde parei\n\nx\n\n## Próximo passo\n\nFazer a tela.\nDepois testar.\n\n"
        "## Outro\n\ny\n",
        encoding="utf-8",
    )
    second = workspace / "projects" / "beta"
    second.mkdir()
    (second / "CONTINUE.md").write_text("# Continuar\n\n## Onde parei\n\nx\n", encoding="utf-8")
    (workspace / "projects" / "gamma").mkdir()
    result = _collect(roots, workspace)
    assert result["next_steps"] == [{"project": "alpha", "text": "Fazer a tela.\nDepois testar."}]
    assert any("beta" in warning for warning in result["warnings"])
    assert not any("gamma" in warning for warning in result["warnings"])


def test_last_activity_uses_the_stale_window(roots, workspace, fake_gh, home, make_repo, commit):
    repo = make_repo("app")
    commit(repo, "feat(TS-2): oldest", "2026-10-15")
    commit(repo, "feat(TS-1): old", "2026-10-20")
    commit(repo, "feat(TS-1): newer", "2026-10-22")
    commit(repo, "feat(TS-3): friday", "2026-10-23")
    result = _collect(roots, workspace, stale=3)
    assert result["last_activity"] == {"TS-1": "2026-10-22", "TS-3": "2026-10-23"}
    assert [c["subject"] for c in result["commits"]] == ["feat(TS-3): friday"]
    wider = _collect(roots, workspace, stale=8)
    assert wider["last_activity"]["TS-2"] == "2026-10-15"


def test_a_broken_repo_is_a_warning(roots, workspace, fake_gh, home, make_repo, commit):
    commit(make_repo("good"), "feat(TS-1): x", "2026-10-26")
    broken = roots / "broken"
    broken.mkdir()
    (broken / ".git").write_text("gitdir: elsewhere\n", encoding="utf-8")
    result = _collect(roots, workspace)
    assert [c["repo"] for c in result["commits"]] == ["good"]
    assert any("broken" in warning for warning in result["warnings"])


def test_cli_prints_json(
    roots, workspace, fake_gh, home, make_repo, commit, tmp_path, monkeypatch, capsys
):
    config = tmp_path / "ws-config"
    config.mkdir()
    (config / "config.toml").write_text(
        f'[jira]\nsite = "https://example.atlassian.net"\nemail = "dev@example.com"\n'
        f'[standup]\nrepo_roots = ["{roots}"]\n',
        encoding="utf-8",
    )
    monkeypatch.setenv("WS_CONFIG_DIR", str(config))
    monkeypatch.setenv("WS_REPO_ROOT", str(workspace))
    commit(make_repo("app"), "feat(TS-1): x", "2026-10-26")
    assert main(["standup", "collect", "--today", "2026-10-26"]) == 0
    out = json.loads(capsys.readouterr().out)
    assert out["window"]["since"] == "2026-10-23"
    assert [c["subject"] for c in out["commits"]] == ["feat(TS-1): x"]


def test_cli_without_config_uses_defaults_and_warns(
    workspace, fake_gh, home, tmp_path, monkeypatch, capsys
):
    monkeypatch.setenv("WS_CONFIG_DIR", str(tmp_path / "no-config"))
    monkeypatch.setenv("WS_REPO_ROOT", str(workspace))
    assert main(["standup", "collect", "--today", "2026-10-26"]) == 0
    out = json.loads(capsys.readouterr().out)
    assert any("config.toml" in warning for warning in out["warnings"])
    assert any(str(home / "repos") in warning for warning in out["warnings"])


def test_cli_invalid_config_exits_2(workspace, home, tmp_path, monkeypatch, capsys):
    config = tmp_path / "ws-config"
    config.mkdir()
    (config / "config.toml").write_text("not = [valid", encoding="utf-8")
    monkeypatch.setenv("WS_CONFIG_DIR", str(config))
    assert main(["standup", "collect"]) == 2
    assert "config.toml" in capsys.readouterr().err


def test_stash_is_not_work(roots, workspace, fake_gh, home, make_repo, commit, git, monkeypatch):
    repo = make_repo("app")
    git(repo, "checkout", "-q", "-b", "feature/TS-1-tela")
    (repo / "file.txt").write_text("one", encoding="utf-8")
    git(repo, "add", "file.txt")
    commit(repo, "feat(TS-1): real work", "2026-10-26")
    (repo / "file.txt").write_text("two", encoding="utf-8")
    monkeypatch.setenv("GIT_AUTHOR_EMAIL", "dev@example.com")
    monkeypatch.setenv("GIT_COMMITTER_EMAIL", "dev@example.com")
    git(repo, "stash", "push", "-q")
    assert "WIP on" in git(repo, "log", "-g", "--format=%s", "refs/stash").stdout
    result = _collect(roots, workspace)
    assert [c["subject"] for c in result["commits"]] == ["feat(TS-1): real work"]
    assert result["last_activity"] == {"TS-1": "2026-10-26"}


def test_merge_commits_are_kept(
    roots, workspace, fake_gh, home, make_repo, commit, git, monkeypatch
):
    monkeypatch.setenv("GIT_AUTHOR_EMAIL", "dev@example.com")
    monkeypatch.setenv("GIT_COMMITTER_EMAIL", "dev@example.com")
    repo = make_repo("app")
    commit(repo, "feat(TS-1): base", "2026-10-24")
    git(repo, "checkout", "-q", "-b", "feature/TS-2-x")
    commit(repo, "feat(TS-2): side", "2026-10-26")
    git(repo, "checkout", "-q", "-")
    commit(repo, "feat(TS-3): main", "2026-10-26")
    git(repo, "merge", "-q", "--no-ff", "feature/TS-2-x", "-m", "Merge TS-2 into main")
    subjects = [c["subject"] for c in _collect(roots, workspace)["commits"]]
    assert "Merge TS-2 into main" in subjects


def test_odd_line_separator_in_a_subject_does_not_break(
    roots, workspace, fake_gh, home, make_repo, commit
):
    repo = make_repo("app")
    commit(repo, "feat(TS-1): antes\u0085depois", "2026-10-26")
    commit(repo, "feat(TS-2): normal", "2026-10-26")
    subjects = [c["subject"] for c in _collect(roots, workspace)["commits"]]
    assert subjects == ["feat(TS-2): normal", "feat(TS-1): antes\u0085depois"]


def test_non_utf8_branch_name_is_read_with_replacement(
    roots, workspace, fake_gh, home, make_repo, commit, git
):
    repo = make_repo("app")
    commit(repo, "feat(TS-1): x", "2026-10-26")
    git(repo, "branch", "feature/TS-9-a\udce7\udce3o")
    result = _collect(roots, workspace)
    assert [b["name"] for b in result["branches"]] == ["feature/TS-9-a\ufffd\ufffdo"]


def test_non_utf8_gh_answer_is_read_with_replacement(roots, workspace, fake_gh, home):
    raw = json.dumps(GH_ANSWER).replace("tela de exemplo", "a@@o")
    fake_gh.answer.write_bytes(raw.encode().replace(b"@@", b"\xe7\xe3"))
    result = _collect(roots, workspace)
    assert result["prs"][0]["title"] == "feat(TS-101): a\ufffd\ufffdo"


def _branch_at(git, monkeypatch, repo: Path, name: str, day: str, start: str = "HEAD") -> None:
    monkeypatch.setenv("GIT_COMMITTER_DATE", f"{day}T12:00:00")
    git(repo, "branch", name, start)


def test_branches_keep_recent_tip_or_recent_creation_and_drop_old(
    roots, workspace, fake_gh, home, make_repo, commit, git, monkeypatch
):
    repo = make_repo("app")
    commit(repo, "feat(TS-0): base", "2026-10-10")
    old_tip = git(repo, "rev-parse", "HEAD").stdout.strip()
    _branch_at(git, monkeypatch, repo, "feature/TS-1-old", "2026-10-10")
    _branch_at(git, monkeypatch, repo, "feature/TS-3-created-inside", "2026-10-22")
    git(repo, "checkout", "-q", "-b", "feature/TS-2-recent-tip", old_tip)
    commit(repo, "feat(TS-2): recent", "2026-10-26")
    names = [b["name"] for b in _collect(roots, workspace)["branches"]]
    assert names == ["feature/TS-2-recent-tip", "feature/TS-3-created-inside"]


def test_branch_without_reflog_is_judged_by_its_tip_only(
    roots, workspace, fake_gh, home, make_repo, commit, git, monkeypatch
):
    repo = make_repo("app")
    commit(repo, "feat(TS-0): base", "2026-10-10")
    _branch_at(git, monkeypatch, repo, "feature/TS-1-created-inside", "2026-10-22")
    (repo / ".git" / "logs" / "refs" / "heads" / "feature" / "TS-1-created-inside").unlink()
    assert _collect(roots, workspace)["branches"] == []


def test_branch_of_a_linked_worktree_is_listed_once(
    roots, workspace, fake_gh, home, make_repo, commit, git
):
    repo = make_repo("alpha")
    commit(repo, "feat(TS-5): work", "2026-10-26")
    git(repo, "branch", "feature/TS-5-work")
    git(repo, "worktree", "add", "-q", "-b", "feature/TS-6-other", str(roots / "linked"))
    git(roots / "linked", "config", "user.email", "dev@example.com")
    branches = _collect(roots, workspace)["branches"]
    assert sorted((b["repo"], b["name"]) for b in branches) == [
        ("alpha", "feature/TS-5-work"),
        ("alpha", "feature/TS-6-other"),
    ]


def test_cli_prints_compact_json(
    roots, workspace, fake_gh, home, make_repo, commit, tmp_path, monkeypatch, capsys
):
    config = tmp_path / "ws-config"
    config.mkdir()
    (config / "config.toml").write_text(
        f'[jira]\nsite = "https://example.atlassian.net"\nemail = "dev@example.com"\n'
        f'[standup]\nrepo_roots = ["{roots}"]\n',
        encoding="utf-8",
    )
    monkeypatch.setenv("WS_CONFIG_DIR", str(config))
    monkeypatch.setenv("WS_REPO_ROOT", str(workspace))
    commit(make_repo("app"), "feat(TS-1): ação", "2026-10-26")
    assert main(["standup", "collect", "--today", "2026-10-26"]) == 0
    out = capsys.readouterr().out
    assert out.count("\n") == 1
    assert '"window":{"since":"2026-10-23"' in out
    assert "ação" in out


def test_pr_search_covers_the_stale_window(roots, workspace, fake_gh, home):
    _collect(roots, workspace, stale=8)
    assert "q=is:pr author:@me updated:>=2026-10-14" in fake_gh.args()


def test_section_ends_at_a_level_one_heading():
    text = "## Próximo passo\n\nFazer X.\n\n# Outro título\n\nnão é do passo\n"
    assert _section(text, "## Próximo passo") == "Fazer X."


PERIOD = (date(2026, 10, 19), date(2026, 10, 25))


def _period(roots: Path, workspace: Path, since=PERIOD[0], until=PERIOD[1]) -> dict:
    return collect(
        StandupConfig(repo_roots=(roots,), stale_workdays=3),
        MONDAY,
        workspace,
        since=since,
        until=until,
    )


def _pr_node(number: int, **fields) -> dict:
    node = {
        "number": number,
        "title": f"feat(TS-{number}): pr {number}",
        "state": "MERGED",
        "mergedAt": "2026-10-21T12:00:00Z",
        "createdAt": "2026-10-20T12:00:00Z",
        "closedAt": "2026-10-21T12:00:00Z",
        "updatedAt": "2026-10-21T12:00:00Z",
        "baseRefName": "master",
        "headRefName": f"feature/TS-{number}",
        "url": f"https://github.com/example/app/pull/{number}",
        "repository": {"name": "app"},
    }
    node.update(fields)
    return node


def _page(nodes: list[dict], total: int | None = None, cursor: str | None = None) -> dict:
    return {
        "data": {
            "search": {
                "issueCount": len(nodes) if total is None else total,
                "pageInfo": {"hasNextPage": cursor is not None, "endCursor": cursor},
                "nodes": nodes,
            }
        }
    }


PAGED_GH = """\
#!{python}
import pathlib, sys

base = pathlib.Path({folder!r})
calls = base / "calls.txt"
text = calls.read_text() if calls.exists() else ""
number = text.count("\\n")
calls.write_text(text + " ".join(sys.argv[1:]) + "\\n")
sys.stdout.write((base / "pages" / f"{{number}}.json").read_text())
"""


@pytest.fixture
def paged_gh(tmp_path_factory, monkeypatch):
    """A gh that answers call N with pages/N.json and logs the arguments of every call."""
    folder = tmp_path_factory.mktemp("paged-gh")
    (folder / "pages").mkdir()
    script = folder / "gh"
    script.write_text(PAGED_GH.format(python=sys.executable, folder=str(folder)), encoding="utf-8")
    script.chmod(0o755)
    monkeypatch.setenv("PATH", f"{folder}{os.pathsep}{os.environ['PATH']}")

    class Pages:
        def set(self, *pages: dict) -> None:
            for number, page in enumerate(pages):
                (folder / "pages" / f"{number}.json").write_text(json.dumps(page))

        def calls(self) -> list[str]:
            return (folder / "calls.txt").read_text().splitlines()

    return Pages()


def test_period_commits_on_the_window_edges(
    roots, workspace, fake_gh, home, make_repo, commit, git, monkeypatch
):
    repo = make_repo("app")
    commit(repo, "feat(TS-1): before", "2026-10-18")
    commit(repo, "feat(TS-2): first day", "2026-10-19")
    commit(repo, "feat(TS-3): middle", "2026-10-22")
    monkeypatch.setenv("GIT_AUTHOR_DATE", "2026-10-25T23:30:00")
    monkeypatch.setenv("GIT_COMMITTER_DATE", "2026-10-25T23:30:00")
    git(
        repo,
        "commit",
        "-q",
        "--allow-empty",
        "-m",
        "feat(TS-4): last night",
        "--author=Dev <dev@example.com>",
    )
    commit(repo, "feat(TS-5): after", "2026-10-26")
    result = _period(roots, workspace)
    assert result["window"] == {"since": "2026-10-19", "until": "2026-10-25", "kind": "period"}
    assert sorted(c["subject"][5:9] for c in result["commits"]) == ["TS-2", "TS-3", "TS-4"]
    assert result["last_activity"] == {
        "TS-2": "2026-10-19",
        "TS-3": "2026-10-22",
        "TS-4": "2026-10-25",
    }


def test_period_branches_in_window(
    roots, workspace, fake_gh, home, make_repo, commit, git, monkeypatch
):
    repo = make_repo("app")
    commit(repo, "feat(TS-0): base", "2026-10-10")
    _branch_at(git, monkeypatch, repo, "feature/TS-1-before", "2026-10-10")
    _branch_at(git, monkeypatch, repo, "feature/TS-2-created-inside", "2026-10-21")
    _branch_at(git, monkeypatch, repo, "feature/TS-3-created-after", "2026-10-28")
    names = [b["name"] for b in _period(roots, workspace)["branches"]]
    assert names == ["feature/TS-2-created-inside"]


def test_period_prs_kept_by_created_merged_closed_or_open(roots, workspace, paged_gh, home):
    old = {"createdAt": "2026-09-01T12:00:00Z", "mergedAt": None, "closedAt": None}
    paged_gh.set(
        _page(
            [
                _pr_node(1, mergedAt=None, closedAt=None, state="OPEN"),
                _pr_node(2, **{**old, "mergedAt": "2026-10-22T12:00:00Z"}),
                _pr_node(3, **{**old, "state": "CLOSED", "closedAt": "2026-10-23T12:00:00Z"}),
                _pr_node(4, **{**old, "state": "OPEN"}),
                _pr_node(5, **{**old, "mergedAt": "2026-10-01T12:00:00Z"}),
                _pr_node(
                    6,
                    createdAt="2026-10-27T12:00:00Z",
                    mergedAt="2026-10-27T13:00:00Z",
                    closedAt="2026-10-27T13:00:00Z",
                ),
            ]
        )
    )
    result = _period(roots, workspace)
    assert [pr["number"] for pr in result["prs"]] == [1, 2, 3, 4]
    assert "updated:>=2026-10-19" in paged_gh.calls()[0]


def test_period_prs_paginate_and_warn_over_300(roots, workspace, paged_gh, home):
    paged_gh.set(
        _page([_pr_node(1)], total=350, cursor="c1"),
        _page([_pr_node(2)], total=350, cursor="c2"),
        _page([_pr_node(3)], total=350, cursor="c3"),
    )
    result = _period(roots, workspace)
    assert [pr["number"] for pr in result["prs"]] == [1, 2, 3]
    calls = paged_gh.calls()
    assert len(calls) == 3
    assert "after=c1" in calls[1] and "after=c2" in calls[2]
    assert any("300" in warning for warning in result["warnings"])


def test_period_prs_stop_at_the_last_page(roots, workspace, paged_gh, home):
    paged_gh.set(_page([_pr_node(1)], total=1))
    result = _period(roots, workspace)
    assert len(paged_gh.calls()) == 1
    assert result["warnings"] == []


def test_period_prs_carry_base_created_closed(roots, workspace, paged_gh, home):
    paged_gh.set(_page([_pr_node(7, baseRefName="release")]))
    pr = _period(roots, workspace)["prs"][0]
    assert pr["base"] == "release"
    assert pr["created_at"] == "2026-10-20T12:00:00Z"
    assert pr["closed_at"] == "2026-10-21T12:00:00Z"
    assert pr["merged_at"] == "2026-10-21T12:00:00Z"
    assert pr["keys"] == ["TS-7"]


def test_period_failed_page_keeps_the_pages_read(roots, workspace, paged_gh, home):
    paged_gh.set(_page([_pr_node(1)], total=150, cursor="c1"), {"errors": ["boom"]})
    result = _period(roots, workspace)
    assert [pr["number"] for pr in result["prs"]] == [1]
    assert sum(w.startswith("gh: PRs left out") for w in result["warnings"]) == 1


def test_daily_window_kind_unchanged(roots, workspace, fake_gh, home, make_repo, commit):
    repo = make_repo("app")
    commit(repo, "feat(TS-1): friday", "2026-10-23")
    result = _collect(roots, workspace)
    assert result["window"]["kind"] == "daily"
    assert "createdAt" not in "\n".join(fake_gh.args())
    assert "base" not in result["prs"][0]
    assert [c["subject"] for c in result["commits"]] == ["feat(TS-1): friday"]
