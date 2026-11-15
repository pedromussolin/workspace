import json
import re
import shlex
import shutil
import subprocess
from collections.abc import Callable
from datetime import date
from pathlib import Path

import pytest
from fake_tracker import FakeTracker, make_card
from test_boardconfig import EXAMPLE
from test_card import START_FIELD, claude_settings, world  # noqa: F401

from ws.card import Preview
from ws.cli import main
from ws.config import data_dir
from ws.taskmodel import Status
from ws.tracker.port import TrackerError, TrackerSetup

Git = Callable[..., subprocess.CompletedProcess[str]]

TITLE = "[BACK] Fechar o lote por horário de corte do dia"
BRANCH = "feature/TS-5-fechar-lote-horario-corte-dia"
CODE = "0123456789ab"
MOVE = '+++\nop = "move"\nkey = "TS-5"\nto = "Em andamento"\n+++\n'
PREFIXES = '\n[board.prefix_repos]\nBACK = ["acme-api"]\nFRONT = ["acme-front"]\n'
KEYS = [
    "ref",
    "title",
    "status",
    "start",
    "branch",
    "repos_from",
    "repos",
    "card_change",
    "draft",
    "preview",
    "code",
    "apply",
    "dry_run",
    "problems",
    "warnings",
    "undo",
]


class Roots:
    """`roots/acme-api` and `roots/acme-front`, each with a local bare remote holding `master`."""

    def __init__(self, tmp_path: Path, git: Git):
        self.tmp = tmp_path
        self.git = git
        self.folder = tmp_path / "roots"
        self.folder.mkdir()
        for name in ("acme-api", "acme-front"):
            self._make(name)

    def _make(self, name: str) -> None:
        path = self.path(name)
        path.mkdir()
        self.git(path, "init", "-q", "-b", "master")
        bare = self.tmp / "remotes" / f"{name}.git"
        bare.mkdir(parents=True)
        self.git(bare, "init", "-q", "--bare", "-b", "master")
        self.git(path, "remote", "add", "origin", str(bare))
        (path / "README.md").write_text("first\n", encoding="utf-8")
        self.git(path, "add", "README.md")
        self.git(path, "commit", "-q", "-m", "first")
        self.git(path, "push", "-q", "origin", "master")

    def path(self, name: str) -> Path:
        return self.folder / name

    def worktree(self, name: str, ref: str = "TS-5") -> Path:
        return self.folder / ".worktrees" / f"{name}-{ref}"

    def clone(self, name: str) -> Path:
        """Another clone of the remote, where a colleague pushes."""
        target = self.tmp / "clones" / name
        if not target.exists():
            bare = self.tmp / "remotes" / f"{name}.git"
            self.git(self.tmp, "clone", "-q", str(bare), str(target))
        return target

    def push_commit(self, name: str, file: str = "later.txt", branch: str = "master") -> str:
        clone = self.clone(name)
        (clone / file).write_text("later\n", encoding="utf-8")
        self.git(clone, "add", file)
        self.git(clone, "commit", "-q", "-m", f"add {file}")
        self.git(clone, "push", "-q", "origin", f"HEAD:refs/heads/{branch}")
        return self.git(clone, "rev-parse", "HEAD").stdout.strip()

    def push_branch(self, name: str, branch: str) -> None:
        self.git(self.clone(name), "push", "-q", "origin", f"HEAD:refs/heads/{branch}")

    def current(self, name: str | Path) -> str:
        path = name if isinstance(name, Path) else self.path(name)
        return self.git(path, "branch", "--show-current").stdout.strip()

    def sha(self, name: str | Path, rev: str = "HEAD") -> str:
        path = name if isinstance(name, Path) else self.path(name)
        return self.git(path, "rev-parse", rev).stdout.strip()

    def branches(self, name: str) -> list[str]:
        refs = self.git(self.path(name), "for-each-ref", "--format=%(refname:short)", "refs/heads")
        return refs.stdout.split()

    def upstream(self, name: str, branch: str) -> str | None:
        found = self.git(
            self.path(name), "rev-parse", "--abbrev-ref", f"{branch}@{{upstream}}", check=False
        )
        return found.stdout.strip() if found.returncode == 0 else None

    def board_text(self, extra: str = "") -> str:
        return f'\n[standup]\nrepo_roots = ["{self.folder}"]\n\n{EXAMPLE}{PREFIXES}{extra}'


class StartWorld(Roots):
    def __init__(self, tmp_path: Path, git: Git, config_dir: Path):
        super().__init__(tmp_path, git)
        self.config_dir = config_dir
        self.tasks = tmp_path / "ws-repo" / "projects" / "demo" / "tasks"
        self.tasks.mkdir(parents=True)
        self.tracker = FakeTracker([make_card("TS-5", title=TITLE)])
        self.previews: list[str] = []
        self.write_config()

    def write_config(self, board: bool = True, extra: str = "") -> None:
        text = self.board_text(extra) if board else f'[standup]\nrepo_roots = ["{self.folder}"]\n'
        (self.config_dir / "config.toml").write_text(text, encoding="utf-8")

    def item(self, front: str) -> None:
        text = f'+++\ncard = "TS-5"\n{front}+++\n\n# Fechar o lote\n'
        (self.tasks / "01-close-batch.md").write_text(text, encoding="utf-8")

    def preview(self, argument: str) -> Preview:
        self.previews.append(argument)
        return Preview(0, "Prévia...\n", CODE)


@pytest.fixture
def env(tmp_path: Path, ws_config: Path, git: Git, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("HOME", str(tmp_path))
    found = StartWorld(tmp_path, git, ws_config)
    monkeypatch.setenv("WS_REPO_ROOT", str(tmp_path / "ws-repo"))
    monkeypatch.setattr("ws.tracker.port.open_tracker", lambda: found.tracker)
    monkeypatch.setattr("ws.card.preview", found.preview)
    return found


def start(capsys, *argv: str) -> tuple[int, dict | None, str]:
    code = main(["card", "start", *argv])
    captured = capsys.readouterr()
    return code, (json.loads(captured.out) if captured.out else None), captured.err


def draft_path() -> Path:
    return data_dir() / "cards" / "drafts" / "start-TS-5.md"


def actions(out: dict) -> list[tuple[str, str | None]]:
    return [(repo["name"], repo["action"]) for repo in out["repos"]]


def git_c(path: Path, *rest: str) -> str:
    return " ".join([f"git -C {shlex.quote(str(path))}", *rest])


def untouched(env: StartWorld) -> None:
    for name in ("acme-api", "acme-front"):
        assert env.current(name) == "master"
        assert env.branches(name) == ["master"]


def test_start_cuts_the_branch_from_the_remote_base_and_previews_the_move(env, capsys):
    remote_tip = env.push_commit("acme-api")

    code, out, err = start(capsys, "TS-5")

    assert (code, err) == (0, "")
    assert list(out) == KEYS
    assert out["title"] == TITLE
    assert (out["status"], out["start"]) == ("todo", None)
    assert out["branch"] == BRANCH
    assert out["repos_from"] == "prefix"
    api = env.path("acme-api")
    assert out["repos"] == [
        {
            "name": "acme-api",
            "path": str(api),
            "base": "master",
            "action": "create",
            "worktree": None,
        }
    ]
    assert env.current("acme-api") == BRANCH
    assert env.sha("acme-api") == remote_tip
    assert env.upstream("acme-api", BRANCH) is None
    assert env.branches("acme-front") == ["master"]
    assert out["card_change"] == "move"
    assert Path(out["draft"]).read_text(encoding="utf-8") == MOVE
    assert env.previews == [out["draft"]]
    assert (out["preview"], out["code"]) == ("Prévia...\n", CODE)
    assert out["apply"] == f"ws card apply {shlex.quote(out['draft'])} --approve {CODE}"
    assert (out["dry_run"], out["problems"], out["warnings"]) == (False, [], [])
    assert out["undo"] == [git_c(api, "switch master"), git_c(api, f"branch -D {BRANCH}")]


def test_start_uses_the_item_repos_and_the_flag_overrides(env, capsys):
    env.item('repos = ["acme-front"]\n')

    code, out, _ = start(capsys, "TS-5")

    assert code == 0
    assert out["repos_from"] == "item"
    assert actions(out) == [("acme-front", "create")]
    assert (env.current("acme-front"), env.current("acme-api")) == (BRANCH, "master")

    code, out, _ = start(capsys, "TS-5", "--repo", "acme-api")

    assert code == 0
    assert out["repos_from"] == "flag"
    assert actions(out) == [("acme-api", "create")]
    assert env.current("acme-api") == BRANCH


def test_start_bug_is_fix_and_flags_override_kind_and_desc(env, capsys):
    env.tracker = FakeTracker(
        [make_card("TS-6", title=TITLE, type="bug"), make_card("TS-7", title=TITLE)]
    )

    code, out, _ = start(capsys, "TS-6")

    assert code == 0
    assert out["branch"] == "fix/TS-6-fechar-lote-horario-corte-dia"
    assert env.current("acme-api") == out["branch"]

    code, out, _ = start(capsys, "TS-7", "--kind", "chore", "--desc", "ajuste-lote")

    assert code == 0
    assert out["branch"] == "chore/TS-7-ajuste-lote"
    assert env.current("acme-api") == "chore/TS-7-ajuste-lote"


def test_start_dirty_second_repo_changes_nothing(env, capsys):
    (env.path("acme-front") / "README.md").write_text("work in progress\n", encoding="utf-8")

    code, out, _ = start(capsys, "TS-5", "--repo", "acme-api", "--repo", "acme-front")

    assert code == 1
    assert len(out["problems"]) == 1
    assert "acme-front has uncommitted changes" in out["problems"][0]
    assert "--worktree" in out["problems"][0]
    assert env.current("acme-api") == "master"
    assert env.branches("acme-api") == ["master"]
    assert (out["draft"], out["preview"], out["code"], out["apply"]) == (None, None, None, None)
    assert out["undo"] == []
    assert env.previews == []
    assert not draft_path().exists()


def test_start_without_repos_names_the_three_ways(env, capsys):
    env.tracker = FakeTracker([make_card("TS-5", title="Sem prefixo")])

    code, out, _ = start(capsys, "TS-5")

    assert code == 1
    assert out["repos_from"] == "none"
    assert out["repos"] == []
    [problem] = out["problems"]
    for way in ("--repo", "repos = [...]", "[board.prefix_repos]"):
        assert way in problem
    untouched(env)
    assert env.previews == []


def test_start_rerun_reuses_the_branch(env, capsys):
    code, out, _ = start(capsys, "TS-5")
    assert code == 0
    first = env.sha("acme-api")
    env.push_commit("acme-api")

    code, out, _ = start(capsys, "TS-5")

    assert code == 0
    assert actions(out) == [("acme-api", "current")]
    assert env.sha("acme-api") == first
    assert out["undo"] == []
    assert out["code"] == CODE
    assert len(env.previews) == 2


def test_start_rerun_with_work_on_the_branch_is_fine(env, capsys):
    start(capsys, "TS-5")
    (env.path("acme-api") / "README.md").write_text("work in progress\n", encoding="utf-8")

    code, out, _ = start(capsys, "TS-5")

    assert code == 0
    assert actions(out) == [("acme-api", "current")]
    assert (env.path("acme-api") / "README.md").read_text(encoding="utf-8") == "work in progress\n"


def test_start_tracks_a_branch_only_on_origin(env, capsys):
    pushed = env.push_commit("acme-api", file="other.txt", branch="feature/TS-5-outro-nome")
    env.push_branch("acme-api", "feature/TS-5-outro-nome-sdbx")

    code, out, _ = start(capsys, "TS-5")

    assert code == 0
    assert out["branch"] == "feature/TS-5-outro-nome"
    assert actions(out) == [("acme-api", "track")]
    assert env.current("acme-api") == "feature/TS-5-outro-nome"
    assert env.sha("acme-api") == pushed != env.sha("acme-api", "origin/master")
    assert env.upstream("acme-api", "feature/TS-5-outro-nome") == "origin/feature/TS-5-outro-nome"
    assert "feature/TS-5-outro-nome-sdbx" not in env.branches("acme-api")
    [warning] = out["warnings"]
    assert "feature/TS-5-outro-nome" in warning and BRANCH in warning
    api = env.path("acme-api")
    assert out["undo"] == [
        git_c(api, "switch master"),
        git_c(api, "branch -D feature/TS-5-outro-nome"),
    ]


def test_start_switches_back_to_the_local_branch_without_resetting_it(env, capsys):
    start(capsys, "TS-5")
    api = env.path("acme-api")
    first = env.sha("acme-api")
    env.git(api, "switch", "-q", "master")
    env.push_commit("acme-api")

    code, out, _ = start(capsys, "TS-5")

    assert code == 0
    assert actions(out) == [("acme-api", "reuse")]
    assert (env.current("acme-api"), env.sha("acme-api")) == (BRANCH, first)
    assert out["undo"] == [git_c(api, "switch master")]


def test_start_failed_fetch_changes_nothing(env, capsys):
    env.git(env.path("acme-front"), "remote", "set-url", "origin", str(env.tmp / "gone.git"))

    code, out, _ = start(capsys, "TS-5", "--repo", "acme-api", "--repo", "acme-front")

    assert code == 1
    [problem] = out["problems"]
    assert problem.startswith("acme-front: git fetch")
    untouched(env)
    assert env.previews == []


def test_start_two_task_branches_is_a_problem(env, capsys):
    env.git(env.path("acme-api"), "branch", "feature/TS-5-um")
    env.git(env.path("acme-front"), "branch", "fix/TS-5-dois")

    code, out, _ = start(capsys, "TS-5", "--repo", "acme-api", "--repo", "acme-front")

    assert code == 1
    [problem] = out["problems"]
    assert "feature/TS-5-um" in problem and "fix/TS-5-dois" in problem
    assert "--kind" in problem and "--desc" in problem
    assert (env.current("acme-api"), env.current("acme-front")) == ("master", "master")
    assert env.previews == []


def test_start_explicit_kind_or_desc_never_hides_the_tasks_branch(env, capsys):
    env.git(env.path("acme-api"), "branch", "feature/TS-5-outro-nome")

    for flags in (["--desc", "ajuste-lote"], ["--kind", "chore"]):
        code, out, _ = start(capsys, "TS-5", *flags)

        assert code == 1
        assert out["problems"] == [
            "TS-5 already has the branch feature/TS-5-outro-nome; drop --kind/--desc to reuse "
            "it, or remove it first"
        ]
        assert out["warnings"] == []
        assert env.current("acme-api") == "master"
        assert env.previews == []

    code, out, _ = start(capsys, "TS-5", "--kind", "feature", "--desc", "outro-nome")

    assert (code, out["warnings"]) == (0, [])
    assert env.current("acme-api") == "feature/TS-5-outro-nome"


def test_start_repo_in_the_middle_of_a_rebase_changes_nothing(env, capsys):
    front = env.path("acme-front")
    env.git(front, "rebase", "--exec", "false", "--root", check=False)
    argv = ["TS-5", "--repo", "acme-api", "--repo", "acme-front"]

    code, out, _ = start(capsys, *argv)

    assert code == 1
    [problem] = out["problems"]
    assert problem.startswith(f"acme-front is in the middle of a rebase in {front}")
    assert "--worktree" in problem
    assert (env.current("acme-api"), env.branches("acme-api")) == ("master", ["master"])
    assert env.branches("acme-front") == ["master"]
    assert env.previews == []
    assert not draft_path().exists()

    code, out, _ = start(capsys, *argv, "--worktree")

    assert code == 0, out["problems"]
    assert actions(out) == [("acme-api", "worktree"), ("acme-front", "worktree")]


def test_start_in_progress_with_a_start_date_writes_no_draft(env, capsys):
    card = make_card("TS-5", title=TITLE, status=Status.IN_PROGRESS, start=date(2026, 11, 10))
    env.tracker = FakeTracker([card])

    code, out, _ = start(capsys, "TS-5")

    assert code == 0
    assert (out["status"], out["start"]) == ("in_progress", "2026-11-10")
    assert out["card_change"] is None
    assert (out["draft"], out["preview"], out["code"], out["apply"]) == (None, None, None, None)
    assert env.previews == []
    assert not draft_path().exists()
    assert env.current("acme-api") == BRANCH


def test_start_in_progress_without_a_start_date_drafts_the_tracker_today(env, capsys):
    card = make_card("TS-5", title=TITLE, status=Status.REVIEW)
    env.tracker = FakeTracker([card], today=date(2026, 1, 2))

    code, out, _ = start(capsys, "TS-5")

    assert code == 0
    assert out["card_change"] == "start"
    assert Path(out["draft"]).read_text(encoding="utf-8") == (
        '+++\nop = "edit"\nkey = "TS-5"\nstart = 2026-01-02\n+++\n'
    )
    assert env.previews == [out["draft"]]


def test_start_without_the_start_date_capability_warns_and_drafts_nothing(env, capsys):
    card = make_card("TS-5", title=TITLE, status=Status.IN_PROGRESS)
    env.tracker = FakeTracker([card], capabilities=())

    code, out, _ = start(capsys, "TS-5")

    assert code == 0
    assert out["card_change"] is None
    assert any("start date" in warning for warning in out["warnings"])
    assert env.previews == []


def test_start_refuses_a_done_card_and_someone_elses_card(env, capsys):
    env.tracker = FakeTracker(
        [
            make_card("TS-5", title=TITLE, status=Status.DONE),
            make_card("TS-6", title=TITLE, assignee="acc-other", reporter="acc-other"),
        ]
    )

    code, out, _ = start(capsys, "TS-5")

    assert code == 1
    assert out["problems"] == ["card is done: reopen it in the tracker first"]

    code, out, _ = start(capsys, "TS-6")

    assert code == 1
    [problem] = out["problems"]
    assert "TS-6 is not yours" in problem
    untouched(env)
    assert env.previews == []


def test_start_refuses_an_epic_and_a_missing_card(env, capsys):
    env.tracker = FakeTracker([make_card("TS-5", title=TITLE, level=1)])

    code, out, _ = start(capsys, "TS-5")

    assert code == 1
    assert "not a card" in out["problems"][0]

    code, out, _ = start(capsys, "TS-9")

    assert code == 1
    assert out["problems"] == ["TS-9 was not found in the tracker's project"]
    untouched(env)


def test_start_missing_base_names_the_config_key(env, capsys):
    env.write_config(extra='\n[board.repos."acme-api"]\nbase = "main"\n')

    code, out, _ = start(capsys, "TS-5")

    assert code == 1
    assert out["problems"] == [
        'origin/main does not exist in acme-api; set [board.repos."acme-api"] base'
    ]
    assert out["repos"][0]["base"] == "main"
    untouched(env)


def test_start_missing_repo_is_a_problem(env, capsys):
    code, out, _ = start(capsys, "TS-5", "--repo", "acme-api", "--repo", "ghost")

    assert code == 1
    [problem] = out["problems"]
    assert "ghost was not found under" in problem
    assert str(env.folder) in problem and "repo_roots" in problem
    assert [repo["path"] for repo in out["repos"]] == [str(env.path("acme-api")), None]
    untouched(env)


def test_start_partial_failure_prints_undo(env, capsys):
    env.push_commit("acme-front", file="x.txt")
    (env.path("acme-front") / "x.txt").write_text("mine\n", encoding="utf-8")

    code, out, _ = start(capsys, "TS-5", "--repo", "acme-api", "--repo", "acme-front")

    assert code == 1
    [problem] = out["problems"]
    assert problem.startswith("acme-front: ")
    api = env.path("acme-api")
    assert out["undo"] == [git_c(api, "switch master"), git_c(api, f"branch -D {BRANCH}")]
    assert env.current("acme-api") == BRANCH
    assert env.branches("acme-front") == ["master"]
    assert out["draft"] is None
    assert env.previews == []
    assert not draft_path().exists()


def test_start_worktree_leaves_the_checkout_alone(env, capsys):
    (env.path("acme-api") / "README.md").write_text("work in progress\n", encoding="utf-8")
    remote_tip = env.push_commit("acme-api")

    code, out, _ = start(capsys, "TS-5", "--worktree")

    assert code == 0
    tree = env.worktree("acme-api")
    [repo] = out["repos"]
    assert (repo["action"], repo["worktree"]) == ("worktree", str(tree))
    assert env.current(tree) == BRANCH
    assert env.sha(tree) == remote_tip
    assert env.upstream("acme-api", BRANCH) is None
    assert env.current("acme-api") == "master"
    readme = (env.path("acme-api") / "README.md").read_text(encoding="utf-8")
    assert readme == "work in progress\n"
    api = env.path("acme-api")
    assert out["undo"] == [
        git_c(api, f"worktree remove {shlex.quote(str(tree))}"),
        git_c(api, f"branch -D {BRANCH}"),
    ]
    assert env.previews == [out["draft"]]


def test_start_worktree_on_an_existing_branch_never_deletes_it(env, capsys):
    env.git(env.path("acme-api"), "branch", BRANCH)

    code, out, _ = start(capsys, "TS-5", "--worktree")

    assert code == 0
    tree = env.worktree("acme-api")
    [repo] = out["repos"]
    assert (repo["action"], repo["worktree"]) == ("reuse", str(tree))
    assert env.current(tree) == BRANCH
    api = env.path("acme-api")
    assert out["undo"] == [git_c(api, f"worktree remove {shlex.quote(str(tree))}")]


def without_auto_setup(env: StartWorld) -> None:
    env.git(env.path("acme-api"), "config", "branch.autoSetupMerge", "false")


def with_a_second_remote(env: StartWorld) -> None:
    """A fork remote holding the same branch, so git cannot guess the remote from the name."""
    fork = env.tmp / "remotes" / "fork.git"
    env.git(env.tmp, "clone", "-q", "--bare", str(env.tmp / "remotes" / "acme-api.git"), str(fork))
    env.git(env.path("acme-api"), "remote", "add", "fork", str(fork))
    env.git(env.path("acme-api"), "fetch", "-q", "fork")


@pytest.mark.parametrize("setup", [without_auto_setup, with_a_second_remote])
def test_start_worktree_tracks_a_branch_only_on_origin(env, capsys, setup):
    pushed = env.push_commit("acme-api", file="other.txt", branch=BRANCH)
    setup(env)

    code, out, _ = start(capsys, "TS-5", "--worktree")

    assert code == 0, out["problems"]
    tree = env.worktree("acme-api")
    assert actions(out) == [("acme-api", "worktree")]
    assert (env.current(tree), env.sha(tree)) == (BRANCH, pushed)
    assert env.upstream("acme-api", BRANCH) == f"origin/{BRANCH}"
    api = env.path("acme-api")
    assert out["undo"] == [
        git_c(api, f"worktree remove {shlex.quote(str(tree))}"),
        git_c(api, f"branch -D {BRANCH}"),
    ]


def test_start_worktree_folder_taken_is_a_problem(env, capsys):
    tree = env.worktree("acme-api")
    tree.mkdir(parents=True)
    (tree / "notes.txt").write_text("mine\n", encoding="utf-8")

    code, out, _ = start(capsys, "TS-5", "--worktree")

    assert code == 1
    [problem] = out["problems"]
    assert str(tree) in problem
    assert env.branches("acme-api") == ["master"]


def test_start_branch_in_another_worktree_is_elsewhere(env, capsys):
    start(capsys, "TS-5", "--worktree")
    tree = env.worktree("acme-api")

    code, out, _ = start(capsys, "TS-5")

    assert code == 0
    [repo] = out["repos"]
    assert repo["action"] == "elsewhere"
    assert Path(repo["worktree"]).resolve() == tree.resolve()
    assert env.current("acme-api") == "master"
    assert any(str(tree.resolve()) in warning for warning in out["warnings"])
    assert out["undo"] == []

    code, out, _ = start(capsys, "TS-5", "--worktree")

    assert code == 0
    assert actions(out) == [("acme-api", "current")]
    assert out["undo"] == []


def test_start_worktree_deleted_by_hand_asks_for_a_prune(env, capsys):
    start(capsys, "TS-5", "--worktree")
    tree = env.worktree("acme-api")
    shutil.rmtree(tree)

    for argv in (["TS-5", "--worktree"], ["TS-5"]):
        code, out, _ = start(capsys, *argv)

        assert code == 1
        [problem] = out["problems"]
        assert "no longer exists" in problem
        assert git_c(env.path("acme-api"), "worktree prune") in problem
    assert env.current("acme-api") == "master"


def test_start_dry_run_changes_nothing(env, capsys):
    code, out, _ = start(capsys, "TS-5", "--dry-run")

    assert code == 0
    assert out["dry_run"] is True
    assert out["branch"] == BRANCH
    assert actions(out) == [("acme-api", "create")]
    assert out["card_change"] == "move"
    assert (out["draft"], out["preview"], out["code"], out["apply"]) == (None, None, None, None)
    assert out["undo"] == []
    untouched(env)
    assert env.previews == []
    assert not draft_path().exists()


def test_start_empty_item_repos_does_only_the_card(env, capsys):
    env.item("repos = []\n")

    code, out, _ = start(capsys, "TS-5")

    assert code == 0
    assert (out["repos_from"], out["repos"], out["branch"]) == ("item", [], None)
    assert Path(out["draft"]).read_text(encoding="utf-8") == MOVE
    assert env.previews == [out["draft"]]
    untouched(env)


def test_start_without_board_exits_2(env, capsys):
    env.write_config(board=False)

    code, out, err = start(capsys, "TS-5")

    assert code == 2
    assert out is None
    assert err.startswith("ws card start: ") and "[board]" in err
    untouched(env)


def test_start_tracker_setup_exits_2_and_tracker_error_exits_3(env, capsys, monkeypatch):
    def setup_missing():
        raise TrackerSetup("no Jira API key")

    monkeypatch.setattr("ws.tracker.port.open_tracker", setup_missing)
    code, out, err = start(capsys, "TS-5")
    assert (code, out, err) == (2, None, "ws card start: no Jira API key\n")

    class Broken(FakeTracker):
        def card(self, ref):
            raise TrackerError("Jira answered 500")

    monkeypatch.setattr("ws.tracker.port.open_tracker", lambda: Broken())
    code, out, err = start(capsys, "TS-5")
    assert (code, out, err) == (3, None, "ws card start: Jira answered 500\n")
    untouched(env)


def test_start_title_without_slug_asks_for_desc(env, capsys):
    env.tracker = FakeTracker([make_card("TS-5", title="[BACK] De a para o")])

    code, out, _ = start(capsys, "TS-5")

    assert code == 1
    assert out["problems"] == ["the title gives no slug; pass --desc"]
    untouched(env)

    code, out, _ = start(capsys, "TS-5", "--desc", "lote")

    assert code == 0
    assert out["branch"] == "feature/TS-5-lote"


@pytest.mark.parametrize(
    ("argv", "fragment"),
    [
        (["ts-5"], "'ts-5' is not a card reference"),
        (["TS-5", "--desc", "Lote"], "--desc 'Lote'"),
        (["TS-5", "--desc", "a" * 41], "at most 40"),
        (["TS-5", "--desc", "lote-sdbx"], "-sdbx"),
        (["TS-5", "--repo", "../acme-api"], "--repo '../acme-api' is not a repo name"),
    ],
)
def test_start_refuses_bad_input_before_anything(env, capsys, argv, fragment):
    code, out, _ = start(capsys, *argv)

    assert code == 1
    assert any(fragment in problem for problem in out["problems"])
    untouched(env)
    assert env.tracker.reads == []


def test_start_title_slug_ending_in_sdbx_is_refused(env, capsys):
    env.tracker = FakeTracker([make_card("TS-5", title="[BACK] Ajustar sdbx")])

    code, out, _ = start(capsys, "TS-5")

    assert code == 1
    assert out["problems"] == [
        "the branch feature/TS-5-ajustar-sdbx would end in -sdbx, the sandbox copy's suffix; "
        "pass another --desc"
    ]
    untouched(env)


def test_start_preview_refusal_keeps_the_branches(env, capsys, monkeypatch):
    monkeypatch.setattr(
        "ws.card.preview", lambda argument: Preview(1, "Nada foi enviado. Problemas:\n", None)
    )

    code, out, _ = start(capsys, "TS-5")

    assert code == 1
    assert out["preview"] == "Nada foi enviado. Problemas:\n"
    assert (out["code"], out["apply"]) == (None, None)
    assert any("preview" in problem for problem in out["problems"])
    assert env.current("acme-api") == BRANCH
    assert out["draft"] is not None


def jira_roots(ws_config: Path, tmp_path: Path, git: Git, monkeypatch) -> Roots:
    roots = Roots(tmp_path, git)
    with (ws_config / "config.toml").open("a", encoding="utf-8") as config:
        config.write(roots.board_text())
    (tmp_path / "ws-repo" / "projects").mkdir(parents=True)
    monkeypatch.setenv("WS_REPO_ROOT", str(tmp_path / "ws-repo"))
    return roots


def test_start_through_jira_without_a_start_date_field_drafts_nothing(
    world,  # noqa: F811
    ws_config,
    tmp_path,
    git,
    monkeypatch,
    capsys,
):
    config = ws_config / "config.toml"
    text = config.read_text(encoding="utf-8").replace(f'start_date_field = "{START_FIELD}"\n', "")
    config.write_text(text, encoding="utf-8")
    in_progress = {"name": "Em andamento", "statusCategory": {"key": "indeterminate"}}
    world.set_card("TS-101", status=in_progress, **{START_FIELD: None})
    roots = jira_roots(ws_config, tmp_path, git, monkeypatch)

    code, out, err = start(capsys, "TS-101")

    assert (code, err) == (0, ""), out
    assert (out["card_change"], out["draft"], out["preview"]) == (None, None, None)
    assert any("cannot set a start date" in warning for warning in out["warnings"])
    assert roots.current("acme-front") == "feature/TS-101-tela-exemplo"
    assert world.writes() == []


@pytest.mark.parametrize("zone", [None, ""])
def test_start_through_jira_without_a_time_zone_exits_3(
    world,  # noqa: F811
    ws_config,
    tmp_path,
    git,
    monkeypatch,
    capsys,
    zone,
):
    world.set_card("TS-101", status={"name": "Tarefas", "statusCategory": {"key": "new"}})
    world.set_myself(zone)
    roots = jira_roots(ws_config, tmp_path, git, monkeypatch)

    code, out, err = start(capsys, "TS-101")

    assert (code, out) == (3, None)
    assert err.startswith("ws card start: unusable tracker time zone")
    assert roots.branches("acme-front") == ["master"]


def test_start_through_the_jira_adapter_and_the_real_preview(
    world,  # noqa: F811
    ws_config,
    tmp_path,
    git,
    monkeypatch,
    capsys,
):
    world.set_card("TS-101", status={"name": "Tarefas", "statusCategory": {"key": "new"}})
    roots = jira_roots(ws_config, tmp_path, git, monkeypatch)

    code, out, err = start(capsys, "TS-101")

    assert (code, err) == (0, ""), out
    assert out["branch"] == "feature/TS-101-tela-exemplo"
    assert out["repos_from"] == "prefix"
    assert roots.current("acme-front") == "feature/TS-101-tela-exemplo"
    assert re.fullmatch(r"[0-9a-f]{12}", out["code"])
    assert (data_dir() / "cards" / "pending" / f"{out['code']}.json").exists()
    assert out["preview"].startswith("Prévia de 1 mudança(s)")
    assert world.writes() == []
