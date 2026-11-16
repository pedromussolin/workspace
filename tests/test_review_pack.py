"""`ws review pack`: the review package of a card, read-only on its repos, private on disk."""

import hashlib
import json
import os
import shlex
import stat
import subprocess
from collections.abc import Callable
from datetime import datetime
from pathlib import Path

import pytest
from fake_tracker import FakeTracker, make_card
from test_card_start import Roots

from ws import reviewpack
from ws.cli import main
from ws.config import data_dir
from ws.taskmodel import Status
from ws.tracker.jira.adapter import JIRA_CAPABILITIES
from ws.tracker.port import TrackerError, TrackerSetup

Git = Callable[..., subprocess.CompletedProcess[str]]

TITLE = "[BACK] Fechar o lote por horário de corte do dia"
BRANCH = "feature/TS-5-fechar-lote"
DESCRIPTION = "Fechar o lote.\n\n## Pronto quando\n- lote fecha às 18h\n\n## Notas\n- nada\n"
VERSIONS = "app/alembic/versions"
A1 = f"{VERSIONS}/0001_inicio.py"
B2 = f"{VERSIONS}/0002_lote.py"
C3 = f"{VERSIONS}/0003_lote.py"
ROUTE = "app/api/routes/lote.py"
TEST = "tests/test_lote.py"
TEST_TEXT = "def test_lote():\n    assert True\n"
DIFF_FLAGS = "-c diff.autoRefreshIndex=false diff --no-ext-diff --no-textconv -M"
THREE_WAYS = (
    "no repos for TS-5: pass --repo NAME, add repos = [...] to its item under "
    "projects/<slug>/tasks/, or list a title prefix in [board.prefix_repos]"
)
KEYS = [
    "ref",
    "card",
    "project",
    "folder",
    "pack_path",
    "review_path",
    "generated_at",
    "repos_from",
    "repos",
    "flags",
    "problems",
    "warnings",
]
REPO_KEYS = [
    "name",
    "path",
    "worktree",
    "branch",
    "base",
    "base_ref",
    "fetched",
    "merge_base",
    "diff_command",
    "diff_file",
    "commits",
    "files",
    "by_category",
    "migrations",
    "env",
    "tests",
]
FILE_KEYS = [
    "path",
    "old_path",
    "abs_path",
    "status",
    "added",
    "deleted",
    "binary",
    "stages",
    "hunks",
    "category",
]


def migration(revision: str, down: str | None) -> str:
    return f'revision = "{revision}"\ndown_revision = {down!r}\n'


class PackWorld(Roots):
    """Roots, acme-api's migrations a1 and b2 on master, the item of TS-5 and the tracker."""

    def __init__(self, tmp_path: Path, git: Git, config_dir: Path):
        super().__init__(tmp_path, git)
        self.config_dir = config_dir
        tasks = tmp_path / "ws-repo" / "projects" / "demo" / "tasks"
        tasks.mkdir(parents=True)
        self.item_path = tasks / "01-lote.md"
        self.item('repos = ["acme-api"]\n')
        self.tracker = self.make_tracker()
        self.write_config()
        self.on_master("acme-api", {A1: migration("a1", None), B2: migration("b2", "a1")})

    def make_tracker(self, title: str = TITLE, **options) -> FakeTracker:
        card = make_card("TS-5", title=title, status=Status.IN_PROGRESS)
        return FakeTracker([card], descriptions={"TS-5": DESCRIPTION}, **options)

    def write_config(self, board: bool = True, extra: str = "") -> None:
        text = self.board_text(extra) if board else f'[standup]\nrepo_roots = ["{self.folder}"]\n'
        (self.config_dir / "config.toml").write_text(text, encoding="utf-8")

    def item(self, front: str) -> None:
        text = f'+++\ncard = "TS-5"\n{front}+++\n\n# Fechar o lote\n'
        self.item_path.write_text(text, encoding="utf-8")

    def write(self, where: Path, files: dict[str, str | bytes]) -> None:
        for rel, content in files.items():
            target = where / rel
            target.parent.mkdir(parents=True, exist_ok=True)
            if isinstance(content, bytes):
                target.write_bytes(content)
            else:
                target.write_text(content, encoding="utf-8")

    def commit(self, where: Path, files: dict[str, str | bytes], message: str = "change") -> None:
        self.write(where, files)
        self.git(where, "add", "-A")
        self.git(where, "commit", "-q", "-m", message)

    def on_master(self, name: str, files: dict[str, str | bytes]) -> None:
        path = self.path(name)
        self.commit(path, files, "base")
        self.git(path, "push", "-q", "origin", "master")

    def task_branch(self, name: str = "acme-api") -> Path:
        path = self.path(name)
        self.git(path, "switch", "-q", "-c", BRANCH)
        return path


@pytest.fixture
def env(tmp_path: Path, ws_config: Path, git: Git, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.setenv("WS_DATA_DIR", str(tmp_path / "data"))
    found = PackWorld(tmp_path, git, ws_config)
    monkeypatch.setenv("WS_REPO_ROOT", str(tmp_path / "ws-repo"))
    monkeypatch.setattr("ws.tracker.port.open_tracker", lambda: found.tracker)
    return found


def pack(capsys, *argv: str) -> tuple[int, dict | None, str]:
    code = main(["review", "pack", *argv])
    captured = capsys.readouterr()
    return code, (json.loads(captured.out) if captured.out else None), captured.err


def folder(project: str = "demo", ref: str = "TS-5") -> Path:
    return data_dir() / "projects" / project / "reviews" / ref


def repo_of(out: dict, name: str = "acme-api") -> dict:
    return next(repo for repo in out["repos"] if repo["name"] == name)


def files(repo: dict) -> dict[str, dict]:
    return {change["path"]: change for change in repo["files"]}


def names(out: dict) -> list[str]:
    return [repo["name"] for repo in out["repos"]]


def no_fetch(monkeypatch: pytest.MonkeyPatch) -> list[Path]:
    fetched: list[Path] = []
    monkeypatch.setattr("ws.gittools.fetch", lambda repo, remote: fetched.append(repo))
    return fetched


def test_pack_collects_the_task_branch(env, capsys):
    env.on_master("acme-api", {ROUTE: "def fechar():\n    return 17\n"})
    path = env.task_branch()
    env.commit(path, {C3: migration("c3", "b2")}, "add the lote migration")
    env.write(path, {ROUTE: "def fechar():\n    return 18\n", TEST: TEST_TEXT})

    code, out, err = pack(capsys, "TS-5")

    assert (code, err) == (0, "")
    assert list(out) == KEYS
    assert (out["ref"], out["project"], out["repos_from"]) == ("TS-5", "demo", "item")
    assert out["card"] == {
        "ref": "TS-5",
        "title": TITLE,
        "type": "task",
        "status": Status.IN_PROGRESS.value,
        "done_when": "- lote fecha às 18h",
    }
    assert out["folder"] == str(folder())
    assert out["pack_path"] == str(folder() / "pack.json")
    assert out["review_path"] == str(folder() / "review.md")
    assert datetime.fromisoformat(out["generated_at"]).tzinfo is not None
    assert (out["flags"], out["problems"], out["warnings"]) == ([], [], [])
    repo = repo_of(out)
    assert list(repo) == REPO_KEYS
    merge_base = env.sha("acme-api", "origin/master")
    assert repo["path"] == str(path)
    assert repo["worktree"] == str(path)
    assert (repo["branch"], repo["base"], repo["base_ref"]) == (BRANCH, "master", "origin/master")
    assert (repo["fetched"], repo["merge_base"]) == (True, merge_base)
    assert repo["diff_command"] == f"git -C {shlex.quote(str(path))} {DIFF_FLAGS} {merge_base}"
    diff_file = folder() / "acme-api.diff"
    assert repo["diff_file"] == str(diff_file)
    assert stat.S_IMODE(diff_file.stat().st_mode) == 0o600
    patch = diff_file.read_text(encoding="utf-8")
    assert f"diff --git a/{C3} b/{C3}\nnew file mode 100644\n" in patch
    assert "-    return 17\n+    return 18\n" in patch
    assert f"diff --git a/{TEST} b/{TEST}\nnew file mode 100644\n" in patch
    assert repo["commits"] == [{"sha": env.sha("acme-api"), "subject": "add the lote migration"}]
    changes = files(repo)
    assert list(changes[C3]) == FILE_KEYS
    assert {p: (c["category"], c["stages"]) for p, c in changes.items()} == {
        C3: ("migration", ["committed"]),
        ROUTE: ("contract", ["unstaged"]),
        TEST: ("test", ["untracked"]),
    }
    assert changes[ROUTE]["abs_path"] == str(path / ROUTE)
    assert (changes[ROUTE]["added"], changes[ROUTE]["deleted"]) == (1, 1)
    assert list(repo["by_category"]) == ["test", "migration", "contract"]
    assert repo["by_category"]["contract"] == {"files": 1, "added": 1, "deleted": 1}
    assert repo["migrations"] == {
        "added": [{"path": C3, "revision": "c3", "down_revision": ["b2"]}],
        "changed_existing": [],
        "heads_before": ["b2"],
        "heads_after": ["c3"],
    }
    assert repo["tests"] == {"added": [TEST], "changed": []}
    assert repo["env"] == {"added": [], "removed": []}


def test_pack_writes_private_files_and_overwrites(env, capsys):
    path = env.task_branch()
    env.commit(path, {"app/core/lote.py": "CUTOFF = 18\n"})
    projects = data_dir() / "projects"
    (projects / "demo").mkdir(parents=True, mode=0o755)
    (projects / "demo").chmod(0o755)

    code, out, _ = pack(capsys, "TS-5")

    target = folder()
    assert code == 0
    for each in (projects, projects / "demo", projects / "demo" / "reviews", target):
        assert stat.S_IMODE(each.stat().st_mode) == 0o700, each
    pack_file = target / "pack.json"
    assert stat.S_IMODE(pack_file.stat().st_mode) == 0o600
    assert json.loads(pack_file.read_text(encoding="utf-8")) == out

    (target / "review.md").write_text("# Revisão antiga\n", encoding="utf-8")
    (target / "acme-front.diff").write_text("old\n", encoding="utf-8")
    env.write(path, {TEST: TEST_TEXT})
    code, again, _ = pack(capsys, "TS-5")

    assert code == 0
    assert TEST in files(repo_of(again))
    assert json.loads(pack_file.read_text(encoding="utf-8")) == again
    assert stat.S_IMODE(pack_file.stat().st_mode) == 0o600
    assert sorted(p.name for p in target.iterdir()) == ["acme-api.diff", "pack.json"]
    assert TEST in (target / "acme-api.diff").read_text(encoding="utf-8")


def test_pack_env_var_added(env, capsys):
    env.on_master("acme-api", {"app/core/old.py": 'import os\n\nOLD = os.getenv("LOTE_OLD")\n'})
    path = env.task_branch()
    (path / "app/core/old.py").unlink()
    source = 'import os\n\nCUTOFF = os.getenv("LOTE_CUTOFF_HOUR")\nBANK = os.environ["LOTE_BANK"]\n'
    env.write(path, {"app/core/lote.py": source})

    code, out, _ = pack(capsys, "TS-5")

    repo = repo_of(out)
    assert code == 0
    assert repo["env"] == {
        "added": [
            {"name": "LOTE_BANK", "required": True, "where": ["app/core/lote.py:4"]},
            {"name": "LOTE_CUTOFF_HOUR", "required": False, "where": ["app/core/lote.py:3"]},
        ],
        "removed": ["LOTE_OLD"],
    }
    assert out["flags"] == [
        "acme-api: required env var added: LOTE_BANK; check the Parameter Store",
        "acme-api: code changed with no test file changed",
    ]


def test_pack_untracked_new_migration(env, capsys):
    path = env.task_branch()
    env.write(path, {C3: migration("c3", "b2"), TEST: TEST_TEXT})

    code, out, _ = pack(capsys, "TS-5")

    repo = repo_of(out)
    change = files(repo)[C3]
    assert code == 0
    assert (change["stages"], change["status"], change["category"]) == (
        ["untracked"],
        "added",
        "migration",
    )
    assert repo["migrations"]["added"] == [{"path": C3, "revision": "c3", "down_revision": ["b2"]}]
    assert repo["migrations"]["heads_after"] == ["c3"]
    assert repo["commits"] == []


def test_pack_reads_the_branch_in_another_worktree(env, capsys):
    env.on_master("acme-api", {ROUTE: "def fechar():\n    return 17\n"})
    path = env.path("acme-api")
    tree = env.worktree("acme-api")
    env.git(path, "worktree", "add", "-q", "-b", BRANCH, str(tree), "origin/master")
    env.write(tree, {ROUTE: "def fechar():\n    return 18\n"})
    env.write(path, {"README.md": "dirty on master\n", "app/core/mine.py": "import os\n"})
    env.write(path, {"app/core/other.py": 'import os\n\nX = os.getenv("NOT_THIS_TASK")\n'})

    code, out, _ = pack(capsys, "TS-5")

    repo = repo_of(out)
    worktree = Path(repo["worktree"])
    assert code == 0
    assert worktree.resolve() == tree.resolve()
    assert repo["branch"] == BRANCH
    assert list(files(repo)) == [ROUTE]
    assert files(repo)[ROUTE]["stages"] == ["unstaged"]
    assert files(repo)[ROUTE]["abs_path"] == str(worktree / ROUTE)
    assert repo["env"] == {"added": [], "removed": []}
    assert repo["diff_command"].startswith(f"git -C {shlex.quote(str(worktree))} {DIFF_FLAGS} ")
    patch = Path(repo["diff_file"]).read_text(encoding="utf-8")
    assert "+    return 18\n" in patch
    assert "README" not in patch and "mine.py" not in patch
    assert env.current("acme-api") == "master"


def test_pack_branch_checked_out_nowhere_warns(env, capsys):
    path = env.task_branch()
    env.commit(path, {"app/core/lote.py": "CUTOFF = 18\n", TEST: TEST_TEXT}, "add lote")
    env.git(path, "switch", "-q", "master")
    env.write(path, {"app/core/dirty.py": "DIRTY = 1\n", "README.md": "dirty\n"})

    code, out, _ = pack(capsys, "TS-5")

    repo = repo_of(out)
    assert code == 0
    assert (repo["worktree"], repo["branch"]) == (None, BRANCH)
    assert [(c["path"], c["stages"], c["abs_path"]) for c in repo["files"]] == [
        ("app/core/lote.py", ["committed"], None),
        (TEST, ["committed"], None),
    ]
    assert repo["diff_command"] == (
        f"git -C {shlex.quote(str(path))} {DIFF_FLAGS} {repo['merge_base']} {BRANCH}"
    )
    patch = Path(repo["diff_file"]).read_text(encoding="utf-8")
    assert "+CUTOFF = 18\n" in patch
    assert "dirty" not in patch.lower()
    assert out["warnings"] == [
        f"acme-api: {BRANCH} is not checked out in any work tree; only its commits are read "
        "and abs_path is null"
    ]


def test_pack_repo_without_task_branch_is_a_problem(env, capsys):
    path = env.task_branch()
    env.commit(path, {TEST: TEST_TEXT})

    code, out, _ = pack(capsys, "TS-5", "--repo", "acme-api", "--repo", "acme-front")

    assert code == 1
    assert (out["repos_from"], out["project"]) == ("flag", "demo")
    [problem] = out["problems"]
    assert problem.startswith("acme-front: ") and "ws card start TS-5" in problem
    front = repo_of(out, "acme-front")
    assert (front["branch"], front["merge_base"], front["files"]) == (None, None, [])
    assert front["diff_file"] is None
    assert not (folder() / "acme-front.diff").exists()
    assert list(files(repo_of(out))) == [TEST]
    assert json.loads((folder() / "pack.json").read_text(encoding="utf-8")) == out


def test_pack_without_repos_names_the_three_ways(env, capsys, monkeypatch):
    env.item_path.unlink()
    env.tracker = env.make_tracker(title="Sem prefixo")
    fetched = no_fetch(monkeypatch)

    code, out, _ = pack(capsys, "TS-5")

    assert code == 1
    assert (out["repos_from"], out["repos"], out["project"]) == ("none", [], "standalone")
    assert out["problems"] == [THREE_WAYS]
    assert fetched == []
    assert (folder("standalone") / "pack.json").exists()


def test_pack_card_absent_from_the_tracker_names_the_three_ways(env, capsys, monkeypatch):
    env.item_path.unlink()
    env.tracker = FakeTracker([])
    fetched = no_fetch(monkeypatch)

    code, out, _ = pack(capsys, "TS-5")

    assert code == 1
    assert (out["card"], out["repos"], out["project"]) == (None, [], "standalone")
    assert out["problems"] == ["TS-5 was not found in the tracker's project", THREE_WAYS]
    assert fetched == []


def test_pack_prefix_and_flag_resolution(env, capsys):
    env.item_path.unlink()
    env.task_branch("acme-api")
    env.task_branch("acme-front")

    code, out, _ = pack(capsys, "TS-5")
    assert (code, out["repos_from"], names(out), out["project"]) == (
        0,
        "prefix",
        ["acme-api"],
        "standalone",
    )

    code, out, _ = pack(capsys, "TS-5", "--repo", "acme-front", "--repo", "acme-front")
    assert (code, out["repos_from"], names(out)) == (0, "flag", ["acme-front"])


def test_pack_project_flag_wins(env, capsys):
    env.task_branch()

    code, out, _ = pack(capsys, "TS-5", "--project", "other-project")

    assert code == 0
    assert out["project"] == "other-project"
    assert out["pack_path"] == str(folder("other-project") / "pack.json")
    assert (folder("other-project") / "pack.json").exists()
    assert not folder("demo").exists()


def test_pack_category_override_from_config(env, capsys):
    rules = '\n[board.repos."acme-front"]\nreview_categories = { front = ["src/app/models/**"] }\n'
    env.write_config(extra=rules)
    path = env.task_branch("acme-front")
    env.commit(
        path,
        {
            "src/app/models/lote.ts": "export interface Lote {}\n",
            "src/app/api/lote.ts": "export const url = '/lote';\n",
        },
    )

    code, out, _ = pack(capsys, "TS-5", "--repo", "acme-front")

    repo = repo_of(out, "acme-front")
    assert code == 0
    assert {p: c["category"] for p, c in files(repo).items()} == {
        "src/app/api/lote.ts": "contract",
        "src/app/models/lote.ts": "front",
    }
    assert repo["env"] is None


def test_pack_flags_a_changed_existing_migration(env, capsys):
    path = env.task_branch()
    env.write(path, {B2: migration("b2", "a1") + "# fix\n", C3: migration("c3", "a1")})
    env.write(path, {TEST: TEST_TEXT})

    code, out, _ = pack(capsys, "TS-5")

    repo = repo_of(out)
    assert code == 0
    assert repo["migrations"]["changed_existing"] == [B2]
    assert out["flags"] == [
        f"acme-api: existing migration changed: {B2}",
        "acme-api: more than one Alembic head after the change: b2, c3",
    ]


def test_pack_flags_code_without_tests(env, capsys):
    path = env.task_branch()
    env.commit(path, {"app/core/lote.py": "CUTOFF = 18\n"})

    code, out, _ = pack(capsys, "TS-5")

    assert code == 0
    assert out["flags"] == ["acme-api: code changed with no test file changed"]
    assert repo_of(out)["tests"] == {"added": [], "changed": []}

    env.write(path, {TEST: TEST_TEXT})
    code, out, _ = pack(capsys, "TS-5")

    assert (code, out["flags"]) == (0, [])


def test_pack_fetch_failure_is_a_warning(env, capsys):
    path = env.task_branch()
    env.commit(path, {TEST: TEST_TEXT})
    env.git(path, "remote", "set-url", "origin", str(env.tmp / "missing.git"))

    code, out, _ = pack(capsys, "TS-5")

    repo = repo_of(out)
    assert code == 0
    assert repo["fetched"] is False
    assert repo["merge_base"] == env.sha("acme-api", "origin/master")
    [warning] = out["warnings"]
    assert warning.startswith("acme-api: fetch failed; using the last fetched origin/master: ")


def test_pack_missing_base_names_the_config_key(env, capsys):
    env.write_config(extra='\n[board.repos."acme-api"]\nbase = "main"\n')
    env.task_branch()

    code, out, _ = pack(capsys, "TS-5")

    repo = repo_of(out)
    assert code == 1
    assert out["problems"] == [
        'acme-api: origin/main does not exist; set [board.repos."acme-api"] base'
    ]
    assert (repo["base"], repo["base_ref"], repo["merge_base"], repo["files"]) == (
        "main",
        "origin/main",
        None,
        [],
    )


def test_pack_missing_repo_is_a_problem(env, capsys):
    code, out, _ = pack(capsys, "TS-5", "--repo", "acme-gone")

    assert code == 1
    assert out["problems"] == [
        f"acme-gone: not found under {env.folder}; check the name or [standup] repo_roots"
    ]
    assert repo_of(out, "acme-gone")["path"] is None


def test_pack_card_without_description_capability_warns(env, capsys):
    env.tracker = env.make_tracker(capabilities=JIRA_CAPABILITIES - {"description"})
    path = env.task_branch()
    env.commit(path, {TEST: TEST_TEXT})

    code, out, _ = pack(capsys, "TS-5")

    assert code == 0
    assert out["card"]["done_when"] is None
    assert out["warnings"] == [
        "the tracker gives no card description; read Pronto quando in the tracker"
    ]


def test_pack_renames_keep_the_old_path_and_take_the_new_category(env, capsys):
    lines = "".join(f"VALUE_{n} = {n}\n" for n in range(20))
    env.on_master("acme-api", {"app/models/lote.py": lines, "app/models/order.py": "ORDER = 1\n"})
    path = env.task_branch()
    (path / "app/api/schemas").mkdir(parents=True)
    env.git(path, "mv", "app/models/lote.py", "app/api/schemas/lote.py")
    edited = lines.replace("VALUE_0 = 0", "VALUE_0 = 100").replace("VALUE_1 = 1", "VALUE_1 = 101")
    (path / "app/api/schemas/lote.py").write_text(edited, encoding="utf-8")
    env.git(path, "add", "-A")
    env.git(path, "commit", "-q", "-m", "move lote to the schemas")
    (path / "app/models/order.py").rename(path / "app/api/order.py")
    env.write(path, {TEST: TEST_TEXT})

    code, out, _ = pack(capsys, "TS-5")

    changes = files(repo_of(out))
    assert code == 0
    summary = {
        p: (c["status"], c["old_path"], c["category"], c["stages"]) for p, c in changes.items()
    }
    assert summary == {
        "app/api/schemas/lote.py": ("renamed", "app/models/lote.py", "contract", ["committed"]),
        "app/models/order.py": ("deleted", None, "model", ["unstaged"]),
        "app/api/order.py": ("added", None, "contract", ["untracked"]),
        TEST: ("added", None, "test", ["untracked"]),
    }
    assert changes["app/models/order.py"]["abs_path"] is None


def test_pack_binary_files_are_counted_and_never_read(env, capsys):
    path = env.task_branch()
    logo = b"\x89PNG\r\n\x1a\n\0\0\0\rIHDR"
    blob = b"\0\0import os\nX = os.getenv('BLOB_VAR')\n"
    env.commit(path, {"app/static/logo.png": logo, "app/core/blob.py": blob})
    env.write(path, {f"{VERSIONS}/0004_blob.py": b"\0revision = 'd4'\ndown_revision = 'b2'\n"})
    env.write(path, {TEST: TEST_TEXT})

    def check(out: dict, paths: tuple[str, ...]) -> None:
        repo = repo_of(out)
        for binary in paths:
            change = files(repo)[binary]
            assert (change["binary"], change["added"], change["deleted"], change["hunks"]) == (
                True,
                None,
                None,
                [],
            ), binary
        assert repo["migrations"]["added"] == []
        assert repo["migrations"]["heads_after"] == ["b2"]
        assert repo["env"]["added"] == []
        assert not [w for w in out["warnings"] if "blob" in w]

    code, out, _ = pack(capsys, "TS-5")
    assert code == 0
    check(out, ("app/static/logo.png", "app/core/blob.py", f"{VERSIONS}/0004_blob.py"))

    (path / f"{VERSIONS}/0004_blob.py").unlink()
    (path / TEST).unlink()
    env.git(path, "switch", "-q", "master")
    code, out, _ = pack(capsys, "TS-5")
    assert code == 0
    assert repo_of(out)["worktree"] is None
    check(out, ("app/static/logo.png", "app/core/blob.py"))


def snapshot(env: PackWorld, *paths: Path) -> list[tuple[str, ...]]:
    """The index bytes first, then reads that never refresh the index (no optional locks)."""
    reads = (
        ("rev-parse", "HEAD"),
        ("branch", "--show-current"),
        ("status", "--porcelain", "--untracked-files=all"),
        ("stash", "list"),
        ("worktree", "list", "--porcelain"),
        ("for-each-ref", "refs/heads"),
    )
    found = []
    for path in paths:
        index = path / env.git(path, "rev-parse", "--git-path", "index").stdout.strip()
        digest = hashlib.sha256(index.read_bytes()).hexdigest()
        found.append(
            (digest, *(env.git(path, "--no-optional-locks", *read).stdout for read in reads))
        )
    return found


def stale(*files: Path) -> None:
    """Same content, another timestamp: a plain `git diff` would rewrite the index."""
    for file in files:
        os.utime(file, (1_000_000_000, 1_000_000_000))


def test_pack_never_changes_the_repos(env, capsys):
    env.on_master("acme-api", {"app/core/lote.py": "CUTOFF = 17\n", ROUTE: "ROUTE = 1\n"})
    api = env.task_branch()
    env.commit(api, {"app/core/batch.py": "BATCH = 1\n"})
    env.write(api, {"app/core/lote.py": "CUTOFF = 99\n"})
    env.git(api, "stash", "push", "-q")
    env.write(api, {"app/core/lote.py": "CUTOFF = 18\n", ROUTE: "ROUTE = 2\n"})
    env.git(api, "add", "app/core/lote.py")
    env.write(api, {TEST: TEST_TEXT})
    front = env.path("acme-front")
    tree = env.worktree("acme-front")
    env.git(front, "worktree", "add", "-q", "-b", BRANCH, str(tree), "origin/master")
    env.write(tree, {"src/app/lote.ts": "export const lote = 1;\n"})
    env.write(front, {"README.md": "dirty on master\n"})
    stale(api / "README.md", api / A1, tree / "README.md")
    before = snapshot(env, api, front, tree)

    code, out, _ = pack(capsys, "TS-5", "--repo", "acme-api", "--repo", "acme-front")

    assert (code, out["problems"]) == (0, [])
    assert snapshot(env, api, front, tree) == before
    stages = {p: c["stages"] for p, c in files(repo_of(out)).items()}
    assert stages == {
        "app/core/batch.py": ["committed"],
        "app/core/lote.py": ["staged"],
        ROUTE: ["unstaged"],
        TEST: ["untracked"],
    }
    patch = Path(repo_of(out)["diff_file"]).read_text(encoding="utf-8")
    assert "+CUTOFF = 18\n" in patch and "+ROUTE = 2\n" in patch and "+BATCH = 1\n" in patch
    assert "README" not in patch
    front_patch = Path(repo_of(out, "acme-front")["diff_file"]).read_text(encoding="utf-8")
    assert "+export const lote = 1;\n" in front_patch
    assert not list((env.tmp / "data").glob(".review-index-*"))


def test_pack_reads_another_remote(env, capsys):
    config = env.config_dir / "config.toml"
    text = config.read_text(encoding="utf-8")
    assert 'remote = "origin"' in text
    config.write_text(text.replace('remote = "origin"', 'remote = "upstream"'), encoding="utf-8")
    path = env.task_branch()
    env.git(path, "remote", "rename", "origin", "upstream")
    env.commit(path, {TEST: TEST_TEXT})

    code, out, _ = pack(capsys, "TS-5")

    repo = repo_of(out)
    assert (code, out["problems"]) == (0, [])
    assert (repo["base_ref"], repo["fetched"]) == ("upstream/master", True)
    assert repo["merge_base"] == env.sha("acme-api", "upstream/master")
    assert list(files(repo)) == [TEST]


def test_pack_type_change_is_read(env, capsys):
    env.on_master("acme-api", {"app/core/link.py": "LINK = 1\n", "app/core/real.py": "R = 1\n"})
    path = env.task_branch()
    (path / "app/core/link.py").unlink()
    (path / "app/core/link.py").symlink_to("real.py")
    env.write(path, {TEST: TEST_TEXT})

    code, out, _ = pack(capsys, "TS-5")

    assert (code, out["problems"]) == (0, [])
    change = files(repo_of(out))["app/core/link.py"]
    assert (change["status"], change["stages"], change["hunks"]) == (
        "type_changed",
        ["unstaged"],
        [1],
    )


def test_pack_warns_on_a_merge_in_progress(env, capsys):
    env.on_master("acme-api", {"app/core/c.txt": "a = 0\n"})
    path = env.task_branch()
    env.commit(path, {"app/core/c.txt": "a = 1\n", TEST: TEST_TEXT})
    env.git(path, "switch", "-q", "-c", "other", "master")
    env.commit(path, {"app/core/c.txt": "a = 2\n"})
    env.git(path, "switch", "-q", BRANCH)
    env.git(path, "merge", "-q", "other", check=False)

    code, out, _ = pack(capsys, "TS-5")

    assert code == 0
    assert (
        f"acme-api: a merge is in progress in {path}; the review shows it half done"
        in (out["warnings"])
    )


def test_pack_reads_the_base_tree_once(env, capsys, monkeypatch):
    path = env.task_branch()
    env.commit(path, {"app/core/lote.py": "import os\nX = os.getenv('LOTE')\n", TEST: TEST_TEXT})
    reads: list[str] = []
    real = reviewpack.files_at

    def spy(repo, ref, only=None):
        reads.append(ref)
        return real(repo, ref, only=only)

    monkeypatch.setattr(reviewpack, "files_at", spy)

    code, out, _ = pack(capsys, "TS-5")

    assert code == 0
    assert reads.count(repo_of(out)["merge_base"]) == 1
    assert repo_of(out)["env"]["added"][0]["name"] == "LOTE"


def test_pack_without_board_exits_2(env, capsys):
    env.write_config(board=False)

    code, out, err = pack(capsys, "TS-5")

    assert (code, out) == (2, None)
    assert err.startswith("ws review pack: ") and "[board]" in err
    assert not (data_dir() / "projects").exists()


def test_pack_tracker_error_exits_3(env, capsys, monkeypatch):
    def setup_missing():
        raise TrackerSetup("no tracker key")

    monkeypatch.setattr("ws.tracker.port.open_tracker", setup_missing)
    code, out, err = pack(capsys, "TS-5")
    assert (code, out, err) == (2, None, "ws review pack: no tracker key\n")

    class Broken(FakeTracker):
        def card(self, ref):
            raise TrackerError("the tracker answered 500")

    monkeypatch.setattr("ws.tracker.port.open_tracker", lambda: Broken())
    code, out, err = pack(capsys, "TS-5")
    assert (code, out, err) == (3, None, "ws review pack: the tracker answered 500\n")
    assert not (data_dir() / "projects").exists()


@pytest.mark.parametrize(
    "argv, problem",
    [
        (["ts-5"], "'ts-5' is not a card reference like TS-123"),
        (["TS-5", "--repo", "../acme-api"], "--repo '../acme-api' is not a repo name"),
        (
            ["TS-5", "--project", "../demo"],
            "--project '../demo' must be lowercase words joined by hyphens",
        ),
    ],
)
def test_pack_refuses_bad_input_before_anything(env, capsys, argv, problem):
    code, out, _ = pack(capsys, *argv)

    assert code == 1
    assert out["problems"] == [problem]
    assert (out["pack_path"], out["repos"]) == (None, [])
    assert env.tracker.reads == []
    assert not (data_dir() / "projects").exists()


def test_pack_help_names_the_command(capsys):
    with pytest.raises(SystemExit):
        main(["review", "pack", "--help"])
    assert "--project" in capsys.readouterr().out


def test_pack_never_writes_under_the_workspace_repo(env, capsys):
    path = env.task_branch()
    env.commit(path, {TEST: TEST_TEXT})

    pack(capsys, "TS-5")

    written = [p for p in (env.tmp / "ws-repo").rglob("*") if p.is_file()]
    assert written == [env.item_path]
    assert os.path.commonpath([folder(), data_dir()]) == str(data_dir())
