import json
import os
import shutil
import subprocess
import sys

from adopt_helpers import make_repo, row
from adopt_items.apply import SubprocessRunner, apply, revert_command
from adopt_items.maprows import Link
from adopt_items.plan import build_plan
from item_helpers import ANA, CONFIG, ME, TEMPLATES


def test_real_ws_item_new_and_check(tmp_path, ws_config):
    (ws_config / "config.toml").write_text(CONFIG, encoding="utf-8")
    repo = tmp_path / "repo"
    repo.mkdir()
    shutil.copytree(TEMPLATES, repo / "templates" / "item")
    make_repo(repo, demo={"01-a.md": "# A\n", "01-a-notes.md": "notas\n"})
    rows = [
        row(project="demo", file="tasks/01-a.md", card="TS-1", epic="TS-9"),
        row(
            project="demo", card="novo-a-3", action="criar", heading="Nova", epic="TS-9",
            line=3, scope="porque", done_when="feito",
        ),
        row(project="demo", card="novo-a-4", action="criar", heading="Outra", line=4,
            epic="novo-E1", links=(Link("blocks", "novo-a-3"),)),
        row(project="demo", card="TS-9", type_="epic", line=5),
    ]  # fmt: skip
    people = {"ana": ANA, "bia": ME}
    plan = build_plan(rows, repo, people, [])
    (tmp_path / "map").mkdir()
    runner = SubprocessRunner(repo)
    apply(plan, repo, runner, tmp_path / "map")

    new = (repo / plan.items[1].path).read_text()
    assert 'epic = "TS-9"' in new and "porque" in new and "feito" in new
    pending = (repo / plan.items[2].path).read_text()
    assert "epic" not in pending.split("+++")[1]
    assert 'blocks = ["tasks/' in pending
    first = (repo / "projects/demo/tasks/01-a.md").read_text()
    assert 'docs = ["01-a-notes.md"]' in first

    done = subprocess.run(
        [sys.executable, "-m", "ws", "item", "check"],
        capture_output=True,
        text=True,
        env={**os.environ, "WS_REPO_ROOT": str(repo)},
    )
    assert done.returncode == 0, done.stdout + done.stderr
    assert json.loads(done.stdout)["problems"] == []


def test_the_revert_command_restores_the_tree(tmp_path, ws_config):
    repo = tmp_path / "repo"
    repo.mkdir()
    shutil.copytree(TEMPLATES, repo / "templates" / "item")
    make_repo(repo, demo={"01-a.md": "# A\n"})
    (ws_config / "config.toml").write_text(CONFIG, encoding="utf-8")
    plan = build_plan(
        [row(project="demo", file="tasks/01-a.md", epic="TS-9")], repo, {"ana": ANA, "bia": ME}, []
    )
    apply(plan, repo, SubprocessRunner(repo), tmp_path)
    subprocess.run(revert_command(repo), shell=True, check=True, capture_output=True)
    status = subprocess.run(
        ["git", "-C", str(repo), "status", "--porcelain"], capture_output=True, text=True
    )
    assert status.stdout == ""
