import os
import subprocess
import sys
from pathlib import Path

import pytest
from adopt_helpers import HEADER, FakeRunner, make_repo, tree_hash
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
    assert code == 0 and "item projects/p/tasks/01-a.md" in out
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
