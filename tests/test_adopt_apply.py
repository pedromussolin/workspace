import shutil
import subprocess
from pathlib import Path

import pytest
from adopt_helpers import PEOPLE, FakeRunner, git, make_repo, row, tree_hash
from adopt_items import apply as apply_mod
from adopt_items.apply import ApplyError, apply, precheck, revert_command
from adopt_items.plan import build_plan


def run(tmp_path, repo, rows, runner=None, docs=()):
    plan = build_plan(rows, repo, PEOPLE, list(docs))
    runner = runner or FakeRunner(repo)
    map_dir = tmp_path / "map"
    map_dir.mkdir(exist_ok=True)
    return plan, runner, apply(plan, repo, runner, map_dir)


def repo_of(tmp_path, **projects) -> Path:
    root = tmp_path / "repo"
    root.mkdir()
    return make_repo(root, **projects)


def test_apply_inserts_front_matter_and_keeps_bodies(tmp_path):
    bodies = {"01-a.md": "# A\r\n\r\ncorpo\r\n+++\r\nsem final", "02-b.md": "﻿# B\n"}
    repo = repo_of(tmp_path, p=bodies)
    rows = [
        row(file="tasks/01-a.md", card="TS-1", epic="TS-9"),
        row(file="tasks/02-b.md", card="TS-2", line=3),
    ]
    run(tmp_path, repo, rows)
    for name, body in bodies.items():
        new = (repo / "projects/p/tasks" / name).read_bytes().decode()
        assert new.startswith("+++\n") and new.endswith(body)
    first = (repo / "projects/p/tasks/01-a.md").read_bytes().decode()
    assert 'card = "TS-1"' in first and 'epic = "TS-9"' in first


def test_apply_writes_docs_into_the_front_matter(tmp_path):
    repo = repo_of(tmp_path, p={"01-a.md": "# A\n", "01-a-notes.md": "notes\n"})
    run(tmp_path, repo, [row(file="tasks/01-a.md")])
    text = (repo / "projects/p/tasks/01-a.md").read_text()
    assert 'docs = ["01-a-notes.md"]' in text
    assert (repo / "projects/p/tasks/01-a-notes.md").read_text() == "notes\n"


def test_apply_moves_with_git_mv_then_rewrites_links(tmp_path):
    repo = repo_of(
        tmp_path,
        **{
            "artemis-v2": {"13-m.md": "# M\n", "00-index.md": "[m](13-m.md)\n"},
            "vm-migration": {},
        },
    )
    rows = [row(project="vm-migration", file="tasks/13-m.md", origin_project="artemis-v2")]
    _, runner, _ = run(tmp_path, repo, rows)
    assert runner.calls[1][0] == "git_mv"
    assert [c[0] for c in runner.calls].count("git_mv") == 1
    index = (repo / "projects/artemis-v2/tasks/00-index.md").read_text()
    assert index == "[m](../../vm-migration/tasks/13-m.md)\n"
    assert (repo / "projects/vm-migration/tasks/13-m.md").read_text().endswith("# M\n")


def test_apply_renames_the_folder_and_the_slug(tmp_path):
    repo = repo_of(
        tmp_path,
        **{"operations-screens-migration": {"01-a.md": "# A\n"}, "workspace": {}},
    )
    (repo / "projects/workspace/tasks").mkdir(exist_ok=True)
    (repo / "projects/workspace/tasks/00-n.md").write_text(
        "ver [a](../../operations-screens-migration/tasks/01-a.md)\n"
    )
    git(repo, "add", "-A")
    git(repo, "commit", "-q", "-m", "n")
    rows = [row(project="operations-screens-migration", file="tasks/01-a.md")]
    _, runner, _ = run(tmp_path, repo, rows)
    assert runner.calls[1] == (
        "git_mv",
        "projects/operations-screens-migration",
        "projects/vm-migration",
    )
    assert (repo / "projects/vm-migration/tasks/01-a.md").is_file()
    note = (repo / "projects/workspace/tasks/00-n.md").read_text()
    assert note == "ver [a](../../vm-migration/tasks/01-a.md)\n"


def test_apply_passes_a_slug_for_every_new_item_and_omits_a_pending_epic(tmp_path):
    repo = repo_of(tmp_path, p={})
    rows = [
        row(card="novo-a-2", action="criar", epic="novo-E3"),
        row(card="novo-a-3", action="criar", epic="TS-9", line=3),
    ]
    plan, runner, _ = run(tmp_path, repo, rows)
    news = [c for c in runner.calls if c[0] == "item_new"]
    assert [c[7] for c in news] == [i.slug for i in plan.items]
    assert [c[3] for c in news] == [None, "TS-9"]
    pending = (repo / plan.items[0].path).read_text()
    assert "epic" not in pending.split("+++")[1]


def test_apply_creates_new_items_with_masked_text(tmp_path):
    repo = repo_of(tmp_path, p={})
    rows = [
        row(
            card="novo-a-2", action="criar", heading="o secret", scope="vê secret",
            done_when="feito secret",
        )
    ]  # fmt: skip
    plan, _, _ = run(tmp_path, repo, rows)
    text = (repo / plan.items[0].path).read_text()
    assert "# o SECRET" in text and "vê SECRET" in text and "feito SECRET" in text
    assert "secret" not in text


def test_apply_resolves_novo_links_to_paths(tmp_path):
    from adopt_items.maprows import Link

    repo = repo_of(tmp_path, p={})
    rows = [
        row(card="novo-a-2", action="criar", links=(Link("blocks", "novo-a-3"),)),
        row(card="novo-a-3", action="criar", links=(Link("blocked_by", "novo-a-2"),), line=3),
    ]
    plan, _, _ = run(tmp_path, repo, rows)
    one, two = [(repo / i.path).read_text() for i in plan.items]
    assert f'blocks = ["tasks/{plan.items[1].path.rsplit("/", 1)[1]}"]' in one
    assert f'blocked_by = ["tasks/{plan.items[0].path.rsplit("/", 1)[1]}"]' in two
    assert "docs" not in one


def test_apply_refuses_a_path_that_differs_from_the_plan(tmp_path):
    repo = repo_of(tmp_path, p={})
    plan = build_plan([row(card="novo-a-2", action="criar")], repo, PEOPLE, [])
    runner = FakeRunner(repo)
    original = runner.item_new
    runner.item_new = lambda *a: original(*a).replace("01-", "09-")
    with pytest.raises(ApplyError, match="expected") as err:
        apply(plan, repo, runner, tmp_path)
    assert "revert: git -C" in str(err.value)


def test_apply_writes_project_toml_pending_tsv_and_readme_markers(tmp_path):
    repo = repo_of(tmp_path, p={})
    (repo / "projects/p/README.md").write_text(
        "# p\n\n## Tarefas\n\n| # | T |\n|---|---|\n| 01 | a |\n\nTexto `| x |`\n"
    )
    git(repo, "commit", "-aq", "-m", "r")
    rows = [
        row(card="TS-51", type_="epic", title="Epic"),
        row(card="TS-52", type_="initiative", line=3),
        row(card="novo-a-4", action="criar", epic="novo-E3", line=4, title="[X] a"),
        row(card="novo-a-5", action="criar", epic="TS-51", line=5, title="[FRONT] b"),
    ]
    plan, _, _ = run(tmp_path, repo, rows)
    toml = (repo / "projects/p/project.toml").read_text()
    assert toml == 'epics = ["TS-51"]\ninitiative = "TS-52"\n\n[prefixes]\nTS-51 = "FRONT"\n'
    readme = (repo / "projects/p/README.md").read_text()
    assert readme == (
        "# p\n\n## Tarefas\n\n| # | T |\n|---|---|\n| 01 | a |\n\n"
        "<!-- ws:items -->\n<!-- /ws:items -->\n\nTexto `| x |`\n"
    )
    pending = (tmp_path / "map/adopt-pending.tsv").read_text()
    assert pending == f"{plan.items[0].path}\tnovo-E3\n"


def test_readme_marker_is_not_added_twice_and_a_missing_heading_is_reported(tmp_path):
    repo = repo_of(tmp_path, p={}, q={})
    (repo / "projects/q/README.md").write_text("# q\n\nsem tabela\n")
    git(repo, "commit", "-aq", "-m", "r")
    rows = [row(card="TS-51", type_="epic"), row(project="q", card="TS-52", type_="epic", line=3)]
    _, _, lines = run(tmp_path, repo, rows)
    assert (repo / "projects/q/README.md").read_text() == "# q\n\nsem tabela\n"
    assert "readme markers q: no ## Tarefas heading" in lines
    assert "readme markers p: added" in lines
    marked = (repo / "projects/p/README.md").read_text()
    assert marked.count("ws:items") == 2
    apply_mod.add_markers(repo / "projects/p/README.md")
    assert (repo / "projects/p/README.md").read_text() == marked


def test_apply_prints_the_revert_command_first(tmp_path, capsys):
    repo = repo_of(tmp_path, p={"01-a.md": "# A\n"})
    _, _, lines = run(tmp_path, repo, [row(file="tasks/01-a.md")])
    assert lines[0].startswith("revert:") and "git -C" in lines[0] and "clean" in lines[0]
    assert capsys.readouterr().out.splitlines()[0] == lines[0]


def test_refuses_when_project_toml_exists_or_tree_is_dirty(tmp_path):
    repo = repo_of(tmp_path, p={"01-a.md": "# A\n"})
    rows = [row(file="tasks/01-a.md")]
    before = tree_hash(repo)
    plan = build_plan(rows, repo, PEOPLE, [])
    runner = FakeRunner(repo, clean=False)
    with pytest.raises(ApplyError, match="not clean"):
        apply(plan, repo, runner, tmp_path)
    (repo / "projects/p/project.toml").write_text("epics = []\n")
    before = tree_hash(repo)
    with pytest.raises(ApplyError, match="project.toml"):
        apply(plan, repo, FakeRunner(repo), tmp_path)
    assert tree_hash(repo) == before


def test_refuses_a_file_that_already_has_front_matter(tmp_path):
    repo = repo_of(tmp_path, p={"01-a.md": "+++\ntype = 'task'\n+++\n# A\n"})
    plan = build_plan([row(file="tasks/01-a.md")], repo, PEOPLE, [])
    with pytest.raises(ApplyError, match="front matter"):
        apply(plan, repo, FakeRunner(repo), tmp_path)


def test_check_failure_raises_with_the_output_after_the_work(tmp_path, capsys):
    repo = repo_of(tmp_path, p={"01-a.md": "# A\n"})
    runner = FakeRunner(repo, check=(1, '{"problems": ["x"]}'))
    plan = build_plan([row(file="tasks/01-a.md")], repo, PEOPLE, [])
    with pytest.raises(ApplyError) as err:
        apply(plan, repo, runner, tmp_path)
    assert '"problems"' in str(err.value)
    assert runner.calls[-1] == ("item_check", ("p",))


def test_links_from_a_tracker_false_row_are_reported_and_not_written(tmp_path, capsys):
    from adopt_items.maprows import Link
    from adopt_items.plan import render_plan

    repo = repo_of(tmp_path, p={"01-a.md": "# A\n"})
    rows = [
        row(file="tasks/01-a.md", card="-", action="sem-card", status="a fazer",
            links=(Link("relates", "TS-5570"),)),
    ]  # fmt: skip
    plan, _, lines = run(tmp_path, repo, rows)
    assert len(plan.dropped_links) == 1
    assert "warn: link dropped a.tsv:2 relates:TS-5570" in render_plan(plan)
    assert any(line.startswith("warn: link dropped") for line in lines)
    assert "relates" not in (repo / "projects/p/tasks/01-a.md").read_text()


def test_a_stale_pending_file_is_removed_when_nothing_is_pending(tmp_path):
    repo = repo_of(tmp_path, p={"01-a.md": "# A\n"})
    (tmp_path / "map").mkdir()
    (tmp_path / "map/adopt-pending.tsv").write_text("old\tnovo-E1\n")
    run(tmp_path, repo, [row(file="tasks/01-a.md")])
    assert not (tmp_path / "map/adopt-pending.tsv").exists()


class GitRunner(FakeRunner):
    """FakeRunner that moves with a real `git mv`, as the apply does."""

    def git_mv(self, src: str, dst: str) -> None:
        self.calls.append(("git_mv", src, dst))
        (self.repo / dst).parent.mkdir(parents=True, exist_ok=True)
        git(self.repo, "mv", src, dst)


@pytest.mark.parametrize("with_claude_md", [True, False])
def test_the_revert_command_restores_root_files_the_relink_rewrote(tmp_path, with_claude_md):
    repo = repo_of(tmp_path, **{"operations-screens-migration": {"01-a.md": "# A\n"}})
    link = "[a](projects/operations-screens-migration/tasks/01-a.md)\n"
    (repo / "README.md").write_text(link)
    if with_claude_md:
        (repo / "CLAUDE.md").write_text(link)
    git(repo, "add", "-A")
    git(repo, "commit", "-q", "-m", "root")
    rows = [row(project="operations-screens-migration", file="tasks/01-a.md")]
    _, _, lines = run(tmp_path, repo, rows, runner=GitRunner(repo))
    assert "rewrite README.md" in lines
    assert (repo / "README.md").read_text() == "[a](projects/vm-migration/tasks/01-a.md)\n"
    assert ("rewrite CLAUDE.md" in lines) is with_claude_md
    subprocess.run(revert_command(repo), shell=True, check=True, capture_output=True)
    status = subprocess.run(
        ["git", "-C", str(repo), "status", "--porcelain"], capture_output=True, text=True
    )
    assert status.stdout == ""
    assert (repo / "README.md").read_text() == link


def test_precheck_reads_the_planned_project_toml_with_the_item_loader(tmp_path):
    repo = repo_of(tmp_path, p={"01-a.md": "# A\n"})
    rows = [
        row(file="tasks/01-a.md", epic="TS-51", title="[[X] a"),
        row(card="TS-51", type_="epic", title="Epic", line=3),
    ]
    plan = build_plan(rows, repo, PEOPLE, [])
    assert plan.project_tomls["p"]["prefixes"] == {"TS-51": "[X"}
    problems = precheck(plan, repo, FakeRunner(repo))
    assert [p for p in problems if p.startswith("projects/p/project.toml: ") and "prefix" in p]
    before = tree_hash(repo)
    with pytest.raises(ApplyError, match="prefixes"):
        apply(plan, repo, FakeRunner(repo), tmp_path)
    assert tree_hash(repo) == before


def test_precheck_needs_the_template_of_every_new_item_type(tmp_path):
    repo = repo_of(tmp_path, p={})
    shutil.rmtree(repo / "templates")
    git(repo, "add", "-A")
    git(repo, "commit", "-q", "-m", "no templates")
    rows = [
        row(card="novo-a-2", action="criar", type_="bug"),
        row(card="novo-a-3", action="criar", type_="bug", line=3),
        row(card="novo-a-4", action="criar", type_="feature", line=4),
    ]
    plan = build_plan(rows, repo, PEOPLE, [])
    problems = precheck(plan, repo, FakeRunner(repo))
    assert [p for p in problems if p.startswith("templates/")] == [
        "templates/item/bug.md does not exist: ws item new needs it",
        "templates/item/feature.md does not exist: ws item new needs it",
    ]


def test_a_check_failure_carries_the_revert_command(tmp_path):
    repo = repo_of(tmp_path, p={"01-a.md": "# A\n"})
    plan = build_plan([row(file="tasks/01-a.md")], repo, PEOPLE, [])
    with pytest.raises(ApplyError) as err:
        apply(plan, repo, FakeRunner(repo, check=(1, "{}")), tmp_path)
    assert str(err.value).splitlines()[-1] == f"revert: {revert_command(repo)}"
