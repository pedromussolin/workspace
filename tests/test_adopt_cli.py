import os
import subprocess
import sys
from pathlib import Path

import pytest
from adopt_helpers import HEADER, FakeRunner, git, make_repo, tree_hash
from adopt_items import cli


def write_map(map_dir: Path, *lines: dict) -> None:
    map_dir.mkdir(exist_ok=True)
    rows = []
    for extra in lines:
        base = dict.fromkeys(HEADER, "-")
        base.update(
            card="TS-1", action="manter", type="Tarefa", title="T", status="a fazer",
            assignee="ana", reporter="bia", project="p",
        )  # fmt: skip
        base.update(extra)
        rows.append("\t".join(base[c] for c in HEADER))
    (map_dir / "a.tsv").write_text("\n".join(["\t".join(HEADER), *rows]) + "\n")
    (map_dir / "people.toml").write_text('ana = "dev-aaaaaaaaaa"\nbia = "dev-bbbbbbbbbb"\n')


@pytest.fixture
def home(tmp_path, monkeypatch):
    monkeypatch.setenv("HOME", str(tmp_path / "home"))
    return tmp_path / "home"


def setup(base, **extra):
    base.mkdir(exist_ok=True)
    repo = base / "repo"
    repo.mkdir()
    make_repo(repo, p={"01-a.md": "# A\n"})
    write_map(base / "map", {"file": "tasks/01-a.md", **extra})
    return repo, base / "map"


def test_dry_run_writes_nothing(tmp_path, home, capsys):
    repo, map_dir = setup(tmp_path)
    runner = FakeRunner(repo)
    before = tree_hash(repo), tree_hash(map_dir)
    code = cli.main(["--repo", str(repo), "--map", str(map_dir)], runner=runner)
    out = capsys.readouterr().out
    assert code == 0 and "item file projects/p/tasks/01-a.md" in out
    assert (tree_hash(repo), tree_hash(map_dir)) == before
    assert all(call[0] == "is_clean" for call in runner.calls)


def test_dry_run_exit_1_lists_every_problem(tmp_path, home, capsys):
    repo, map_dir = setup(tmp_path, assignee="ghost", reporter="phantom")
    (repo / "projects/p/project.toml").write_text("epics = []\n")
    code = cli.main(["--repo", str(repo), "--map", str(map_dir)], runner=FakeRunner(repo))
    out = capsys.readouterr().out
    assert code == 1
    assert "ghost" in out and "phantom" in out and "project.toml" in out


def test_outside_commands_are_only_printed_without_the_flag(tmp_path, home, capsys):
    repo, map_dir = setup(tmp_path)
    private = home / ".config/workspace/private"
    private.mkdir(parents=True)
    (private / "operations-screens-migration.md").write_text("x")
    data = home / ".local/share/workspace/projects/operations-screens-migration"
    data.mkdir(parents=True)
    args = ["--repo", str(repo), "--map", str(map_dir), "--apply"]
    assert cli.main(args, runner=FakeRunner(repo)) == 0
    out = capsys.readouterr().out
    assert "mv " in out and "vm-migration" in out
    assert (private / "operations-screens-migration.md").exists() and data.exists()

    repo, map_dir = setup(tmp_path / "second")
    args = ["--repo", str(repo), "--map", str(map_dir), "--apply", "--outside"]
    assert cli.main(args, runner=FakeRunner(repo)) == 0
    assert (private / "vm-migration.md").read_text() == "x"
    assert not data.exists() and data.with_name("vm-migration").is_dir()


def test_outside_skips_a_missing_source(tmp_path, home, capsys):
    repo, map_dir = setup(tmp_path)
    args = ["--repo", str(repo), "--map", str(map_dir), "--apply", "--outside"]
    assert cli.main(args, runner=FakeRunner(repo)) == 0
    assert "skipped" in capsys.readouterr().out


def test_check_failure_exits_1_and_prints_the_output(tmp_path, home, capsys):
    repo, map_dir = setup(tmp_path)
    runner = FakeRunner(repo, check=(1, '{"problems": ["boom"]}'))
    code = cli.main(["--repo", str(repo), "--map", str(map_dir), "--apply"], runner=runner)
    assert code == 1 and "boom" in capsys.readouterr().out


def test_script_entry_point_runs_a_dry_run(tmp_path, home):
    repo, map_dir = setup(tmp_path)
    script = Path(__file__).resolve().parents[1] / "scripts" / "adopt-items.py"
    done = subprocess.run(
        [sys.executable, str(script), "--repo", str(repo), "--map", str(map_dir)],
        capture_output=True,
        text=True,
        env={**os.environ, "HOME": str(home)},
    )
    assert done.returncode == 0 and "total:" in done.stdout


def test_dirty_tree_is_a_warning_in_a_dry_run_and_fatal_with_apply(tmp_path, home, capsys):
    repo, map_dir = setup(tmp_path)
    args = ["--repo", str(repo), "--map", str(map_dir)]
    assert cli.main(args, runner=FakeRunner(repo, clean=False)) == 0
    assert "warn: the git tree is not clean" in capsys.readouterr().out
    assert cli.main([*args, "--apply"], runner=FakeRunner(repo, clean=False)) == 1


def test_dry_run_prints_each_problem_of_a_planned_project_toml(tmp_path, home, capsys):
    repo, map_dir = setup(tmp_path)
    write_map(
        map_dir,
        {"file": "tasks/01-a.md", "epic": "TS-51", "title": "[[X] a"},
        {"card": "TS-51", "type": "Epic", "title": "Epic"},
    )
    code = cli.main(["--repo", str(repo), "--map", str(map_dir)], runner=FakeRunner(repo))
    out = capsys.readouterr().out
    assert code == 1
    assert [ln for ln in out.splitlines() if ln.startswith("problem: projects/p/project.toml: ")]


def test_dry_run_shows_every_change(tmp_path, home, capsys):
    repo = tmp_path / "repo"
    repo.mkdir()
    make_repo(repo, p={"01-a.md": "# A\n", "00-index.md": "[a](01-a.md)\n"}, q={})
    (repo / "README.md").write_text("[a](projects/p/tasks/01-a.md)\n")
    (repo / "projects/q/README.md").write_text("# q\n\nsem tabela\n")
    git(repo, "add", "-A")
    git(repo, "commit", "-q", "-m", "root")
    map_dir = tmp_path / "map"
    write_map(
        map_dir,
        {"project": "q", "file": "tasks/01-a.md (p)", "epic": "TS-9"},
        {"project": "q", "card": "novo", "action": "criar", "epic": "TS-9", "title": "Nova"},
        {"project": "q", "card": "TS-9", "type": "Epic", "title": "Epic"},
    )
    before = tree_hash(repo)
    code = cli.main(["--repo", str(repo), "--map", str(map_dir)], runner=FakeRunner(repo))
    lines = capsys.readouterr().out.splitlines()
    assert code == 0
    for expected in (
        "move projects/p/tasks/01-a.md -> projects/q/tasks/01-a.md",
        "item file projects/q/tasks/01-a.md card=TS-1 source=a.tsv:2",
        "item new projects/q/tasks/02-new-a-3.md card=- source=a.tsv:3",
        "project.toml projects/q/project.toml",
        '  epics = ["TS-9"]',
        "rewrite README.md",
        "rewrite projects/p/tasks/00-index.md",
        "readme markers q: no ## Tarefas heading",
    ):
        assert expected in lines
    assert tree_hash(repo) == before


def test_outside_alone_only_moves_outside_the_repo(tmp_path, home, capsys):
    repo, map_dir = setup(tmp_path)
    private = home / ".config/workspace/private"
    private.mkdir(parents=True)
    (private / "operations-screens-migration.md").write_text("x")
    data = home / ".local/share/workspace/projects/operations-screens-migration"
    data.mkdir(parents=True)
    runner = FakeRunner(repo)
    before = tree_hash(repo)
    args = ["--repo", str(repo), "--map", str(tmp_path / "no-map"), "--outside"]
    assert cli.main(args, runner=runner) == 0
    out = capsys.readouterr().out
    assert (private / "vm-migration.md").read_text() == "x"
    assert not data.exists() and data.with_name("vm-migration").is_dir()
    assert "outside: mv" in out and "total:" not in out and "item " not in out
    assert tree_hash(repo) == before and runner.calls == []


class BrokenRunner(FakeRunner):
    def __init__(self, repo, error: BaseException, where: str):
        super().__init__(repo)
        self.error, self.where = error, where

    def is_clean(self) -> bool:
        if self.where == "is_clean":
            raise self.error
        return super().is_clean()

    def item_new(self, *args) -> str:
        if self.where == "item_new":
            raise self.error
        return super().item_new(*args)


@pytest.mark.parametrize(
    "error",
    [
        subprocess.CalledProcessError(1, ["ws", "item", "new"], stderr="fatal: boom\n"),
        FileNotFoundError(2, "No such file or directory", "boom"),
    ],
)
def test_an_error_during_apply_prints_it_and_the_revert_command(tmp_path, home, capsys, error):
    repo, map_dir = setup(tmp_path, card="novo", action="criar", file="-")
    args = ["--repo", str(repo), "--map", str(map_dir), "--apply"]
    assert cli.main(args, runner=BrokenRunner(repo, error, "item_new")) == 1
    out = capsys.readouterr().out
    stopped = out[out.index("stopped: ") :]
    assert "boom" in stopped
    assert stopped.rstrip().splitlines()[-1].startswith("revert: git -C")


def test_an_error_before_any_write_prints_no_revert_command(tmp_path, home, capsys):
    repo, map_dir = setup(tmp_path)
    error = subprocess.CalledProcessError(128, ["git", "status"], stderr="fatal: no repo\n")
    args = ["--repo", str(repo), "--map", str(map_dir), "--apply"]
    assert cli.main(args, runner=BrokenRunner(repo, error, "is_clean")) == 1
    out = capsys.readouterr().out
    assert "stopped before writing anything" in out and "fatal: no repo" in out
    assert "revert:" not in out


def test_a_check_failure_repeats_the_revert_command(tmp_path, home, capsys):
    repo, map_dir = setup(tmp_path)
    runner = FakeRunner(repo, check=(1, '{"problems": ["boom"]}'))
    assert cli.main(["--repo", str(repo), "--map", str(map_dir), "--apply"], runner=runner) == 1
    out = capsys.readouterr().out
    assert out.rstrip().splitlines()[-1].startswith("revert: git -C")


def test_dry_run_reports_a_missing_item_template(tmp_path, home, capsys):
    repo, map_dir = setup(tmp_path, card="novo", action="criar", file="-")
    (repo / "templates/item/task.md").unlink()
    git(repo, "commit", "-aq", "-m", "no task template")
    assert cli.main(["--repo", str(repo), "--map", str(map_dir)], runner=FakeRunner(repo)) == 1
    out = capsys.readouterr().out
    assert "problem: templates/item/task.md does not exist" in out
