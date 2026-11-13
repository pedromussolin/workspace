import json

import pytest
from item_helpers import ANA, ME, TEMPLATES, write_item
from item_helpers import item_repo as item_repo

from ws import items
from ws.cli import main
from ws.items import ProjectMissing
from ws.tracker.vocab import CARD_TYPES, required_sections

CLEAN = f'card = "TS-5"\ntype = "task"\nepic = "TS-100"\nassignee = "{ME}"\nreporter = "{ME}"'


def check(capsys, *names):
    code = main(["item", "check", *names])
    out = capsys.readouterr()
    return code, json.loads(out.out) if out.out.strip() else None, out.err


def paths(report):
    return [p["path"] for p in report["problems"]]


def texts(report):
    return [p["problem"] for p in report["problems"]]


def test_check_passes_a_clean_project(item_repo, capsys):
    write_item(item_repo, "01-a.md", CLEAN)

    code, report, _ = check(capsys)

    assert code == 0
    assert report == {"problems": [], "drift": [], "pending": [], "orphans": []}


def test_check_epic_must_be_in_project_toml(item_repo, capsys):
    write_item(item_repo, "01-a.md", CLEAN.replace("TS-100", "TS-9"))

    code, report, _ = check(capsys, "demo")

    assert code == 1
    assert paths(report) == ["projects/demo/tasks/01-a.md"]
    assert texts(report) == ["epic TS-9 is not in project.toml"]


def test_check_unknown_dev_id_names_ws_people_add(item_repo, capsys):
    write_item(item_repo, "01-a.md", CLEAN.replace(ME, "dev-ffffffffff", 1))

    code, report, _ = check(capsys)

    assert code == 1
    assert any("ws people add" in t and "dev-ffffffffff" in t for t in texts(report))


def test_check_known_person_passes(item_repo, capsys):
    write_item(item_repo, "01-a.md", CLEAN.replace(ME, ANA, 1))

    assert check(capsys)[0] == 0


def test_check_docs_must_exist(item_repo, capsys):
    (item_repo / "projects" / "demo" / "tasks" / "01-plan.md").write_text("plano\n")
    write_item(item_repo, "01-a.md", CLEAN + '\ndocs = ["01-plan.md", "02-gone.md"]')

    code, report, _ = check(capsys)

    assert code == 1
    assert len(report["problems"]) == 1
    assert "02-gone.md" in texts(report)[0]


def test_check_link_paths_resolve(item_repo, capsys):
    (item_repo / "projects" / "demo" / "tasks" / "03-doc.md").write_text("sem front matter\n")
    write_item(item_repo, "01-a.md", CLEAN + '\nrelates = ["tasks/03-doc.md"]')
    write_item(item_repo, "02-b.md", f'type = "task"\nassignee = "{ME}"\nreporter = "{ME}"')

    code, report, _ = check(capsys)
    assert code == 1
    assert "tasks/03-doc.md" in texts(report)[0]

    write_item(item_repo, "01-a.md", CLEAN + '\nrelates = ["tasks/02-b.md"]')
    assert check(capsys)[0] == 0


def test_check_link_to_another_projects_item_resolves(item_repo, capsys):
    other = item_repo / "projects" / "other"
    (other / "tasks").mkdir(parents=True)
    (other / "project.toml").write_text('epics = ["TS-7"]\n')
    (other / "tasks" / "02-x.md").write_text(
        f'+++\ncard = "TS-7"\ntype = "task"\nepic = "TS-7"\nassignee = "{ME}"\n'
        f'reporter = "{ME}"\n+++\n# 02 — X\n'
    )
    write_item(item_repo, "01-a.md", CLEAN + '\nblocked_by = ["../other/tasks/02-x.md"]')

    code, report, _ = check(capsys, "demo")
    assert (code, report["problems"]) == (0, [])
    project = items.load_project(item_repo, "demo")
    assert items.link_ref(item_repo, project, "../other/tasks/02-x.md") == "TS-7"
    assert items.link_ref(item_repo, project, "TS-9") == "TS-9"

    for target in ("../ghost/tasks/02-x.md", "../other/tasks/99-none.md", "../../etc/x.md"):
        write_item(item_repo, "01-a.md", CLEAN + f'\nblocked_by = ["{target}"]')
        code, report, _ = check(capsys, "demo")
        assert code == 1
        assert len(report["problems"]) == 1
        assert target in texts(report)[0]


def test_check_link_to_an_untracked_item_is_a_problem(item_repo, capsys):
    write_item(item_repo, "02-b.md", 'tracker = false\nstatus = "todo"')
    write_item(item_repo, "01-a.md", CLEAN + '\nrelates = ["tasks/02-b.md"]')

    code, report, _ = check(capsys)

    assert code == 1
    assert "tasks/02-b.md" in texts(report)[0]


def test_check_cardless_item_without_epic_is_pending_not_a_problem(item_repo, capsys):
    front = f'type = "task"\nassignee = "{ME}"\nreporter = "{ME}"'
    write_item(item_repo, "01-a.md", front)

    code, report, _ = check(capsys)

    assert code == 0
    assert report["problems"] == []
    assert report["pending"] == [
        {"path": "projects/demo/tasks/01-a.md", "card": None, "op": "create", "needs": "epic"}
    ]

    write_item(item_repo, "01-a.md", front + '\nepic = "TS-9"')
    code, report, _ = check(capsys)
    assert code == 1
    assert texts(report) == ["epic TS-9 is not in project.toml"]


def test_check_refuses_one_card_in_two_items(item_repo, capsys):
    write_item(item_repo, "01-a.md", CLEAN)
    write_item(item_repo, "02-b.md", CLEAN)

    code, report, _ = check(capsys)

    assert code == 1
    assert sorted(paths(report)) == ["projects/demo/tasks/01-a.md", "projects/demo/tasks/02-b.md"]
    by_path = {p["path"]: p["problem"] for p in report["problems"]}
    assert by_path["projects/demo/tasks/01-a.md"] == (
        "TS-5 is also the card of projects/demo/tasks/02-b.md"
    )


def test_check_refuses_a_self_link_and_one_target_twice(item_repo, capsys):
    write_item(item_repo, "02-b.md", f'type = "task"\nassignee = "{ME}"\nreporter = "{ME}"')
    write_item(item_repo, "01-a.md", CLEAN + '\nrelates = ["tasks/01-a.md"]')
    code, report, _ = check(capsys)
    assert code == 1
    assert "itself" in texts(report)[0]

    write_item(item_repo, "01-a.md", CLEAN + '\nblocks = ["tasks/02-b.md"]\nrelates = ["TS-8"]')
    assert check(capsys)[0] == 0
    write_item(
        item_repo,
        "01-a.md",
        CLEAN + '\nblocks = ["tasks/02-b.md"]\nblocked_by = ["../demo/tasks/02-b.md"]',
    )
    code, report, _ = check(capsys)
    assert code == 1
    assert "more than one" in texts(report)[0]


def test_check_reports_a_broken_project_toml(item_repo, capsys):
    (item_repo / "projects" / "demo" / "project.toml").write_text('epics = "TS-1"\ncolour = 1\n')

    code, report, _ = check(capsys)

    assert code == 1
    assert set(paths(report)) == {"projects/demo/project.toml"}
    assert any("epics" in t for t in texts(report))
    assert any("colour" in t for t in texts(report))


def test_check_unknown_project_exits_2(item_repo, capsys):
    code, report, err = check(capsys, "ghost")

    assert code == 2
    assert report is None
    assert "ghost" in err


def test_check_without_config_exits_2(item_repo, ws_config, capsys):
    (ws_config / "config.toml").unlink()

    assert check(capsys)[0] == 2


def new(capsys, *args):
    code = main(["item", "new", "demo", *args])
    out = capsys.readouterr()
    return code, out.out.strip(), out.err


def test_new_writes_the_next_number_with_the_template(item_repo, capsys):
    write_item(item_repo, "07-a.md", CLEAN.replace("TS-5", "TS-6"))
    write_item(item_repo, "13-b.md", CLEAN)

    code, out, _ = new(
        capsys,
        "--type",
        "bug",
        "--epic",
        "TS-100",
        "--heading",
        "Fechamento automático",
        "--slug",
        "closing-by-time",
        "--assignee",
        "me",
    )

    assert (code, out) == (0, "projects/demo/tasks/14-closing-by-time.md")
    text = (item_repo / out).read_text(encoding="utf-8")
    assert text.startswith(
        f'+++\ntype = "bug"\nepic = "TS-100"\nassignee = "{ME}"\nreporter = "{ME}"\n+++\n'
        "# 14 — Fechamento automático\n\n"
    )
    headings = [line[3:] for line in text.splitlines() if line.startswith("## ")]
    assert tuple(headings) == required_sections("bug")
    code, report, _ = check(capsys)
    assert (code, report["problems"]) == (0, [])


def test_new_without_slug_folds_the_heading(item_repo, capsys):
    write_item(item_repo, "13-b.md", CLEAN)

    code, out, _ = new(
        capsys,
        "--type",
        "task",
        "--epic",
        "TS-100",
        "--heading",
        "Fechamento automático",
        "--assignee",
        ANA,
    )

    assert (code, out) == (0, "projects/demo/tasks/14-fechamento-automatico.md")
    assert f'assignee = "{ANA}"\nreporter = "{ME}"' in (item_repo / out).read_text("utf-8")


def test_new_folds_only_the_first_six_words(item_repo, capsys):
    code, out, _ = new(
        capsys,
        "--type",
        "task",
        "--epic",
        "TS-100",
        "--heading",
        "Um dois três quatro cinco seis sete oito",
    )

    assert (code, out) == (0, "projects/demo/tasks/01-um-dois-tres-quatro-cinco-seis.md")


def test_new_without_epic_leaves_the_key_out_and_check_reports_pending(item_repo, capsys):
    code, out, _ = new(capsys, "--type", "task", "--heading", "Sem épico")

    assert code == 0
    text = (item_repo / out).read_text(encoding="utf-8")
    assert "epic" not in text.split("+++")[1]
    code, report, _ = check(capsys)
    assert code == 0
    assert report["pending"] == [{"path": out, "card": None, "op": "create", "needs": "epic"}]


@pytest.mark.parametrize(
    "args",
    [
        ["--type", "epic", "--heading", "Algo"],
        ["--type", "task", "--heading", "Algo", "--assignee", "dev-nope"],
        ["--type", "task", "--heading", "Algo", "--reporter", "ana"],
        ["--type", "task", "--heading", "Algo", "--epic", "ts-1"],
        ["--type", "task", "--heading", "Algo", "--slug", "Bad Slug"],
        ["--type", "task", "--heading", ""],
    ],
)
def test_new_refuses_an_epic_type_and_a_bad_dev_id(item_repo, capsys, args):
    code, out, err = new(capsys, *args)

    assert (code, out) == (1, "")
    assert err
    assert list((item_repo / "projects" / "demo" / "tasks").iterdir()) == []


def test_new_in_an_unknown_project_exits_2(item_repo, capsys):
    code = main(["item", "new", "ghost", "--type", "task", "--heading", "Algo"])

    assert code == 2
    assert "ghost" in capsys.readouterr().err


@pytest.mark.parametrize("type_", CARD_TYPES)
def test_item_templates_hold_the_required_sections(type_):
    text = (TEMPLATES / f"{type_}.md").read_text(encoding="utf-8")
    headings = tuple(line[3:] for line in text.splitlines() if line.startswith("## "))

    assert headings == required_sections(type_)


def readme(root):
    return root / "projects" / "demo" / "README.md"


def test_table_rewrites_only_between_the_markers(item_repo, capsys):
    before = "# Demo\n\nantes | x\n\n<!-- ws:items -->\nlixo antigo\n<!-- /ws:items -->\n\ndepois\n"
    readme(item_repo).write_text(before, encoding="utf-8")
    write_item(
        item_repo,
        "14-closing-by-time.md",
        CLEAN + '\n[tracker]\nstatus = "in_progress"',
        "# 14 — Fechamento automático\n",
    )
    write_item(
        item_repo,
        "15-b.md",
        CLEAN.replace("TS-5", "TS-6").replace("task", "feature"),
        "# 15 — A | B\n",
    )

    code = main(["item", "table", "demo"])

    assert code == 0
    assert json.loads(capsys.readouterr().out) == {
        "path": "projects/demo/README.md",
        "rows": 2,
        "changed": True,
    }
    after = readme(item_repo).read_text(encoding="utf-8")
    assert after.startswith("# Demo\n\nantes | x\n\n<!-- ws:items -->\n")
    assert after.endswith("<!-- /ws:items -->\n\ndepois\n")
    assert "lixo" not in after
    assert (
        f"| 14 | [Fechamento automático](tasks/14-closing-by-time.md) | TS-5 | Tarefa | {ME} "
        "| em andamento |\n"
    ) in after
    assert "| 15 | [A \\| B](tasks/15-b.md) | TS-6 | Nova função | " in after
    assert "| # | Tarefa | Card | Tipo | Responsável | Status |" in after


def test_table_fills_an_empty_marker_block_and_keeps_a_hand_table(item_repo, capsys):
    hand = "| Tema | Dono |\n|---|---|\n| x | y |\n\n"
    readme(item_repo).write_text(
        f"# Demo\n\n{hand}<!-- ws:items -->\n<!-- /ws:items -->\n", encoding="utf-8"
    )
    write_item(item_repo, "01-a.md", CLEAN, "# 01 — Algo\n")
    write_item(item_repo, "02-b.md", 'tracker = false\nstatus = "done"', "# 02 — Outro\n")

    assert main(["item", "table", "demo"]) == 0
    assert json.loads(capsys.readouterr().out)["changed"] is True
    text = readme(item_repo).read_text(encoding="utf-8")
    assert text.startswith(f"# Demo\n\n{hand}<!-- ws:items -->\n| # | Tarefa |")
    assert text.endswith("|\n<!-- /ws:items -->\n")
    assert f"| 01 | [Algo](tasks/01-a.md) | TS-5 | Tarefa | {ME} | — |" in text
    assert "| 02 | [Outro](tasks/02-b.md) | — | — | — | concluída |" in text

    assert main(["item", "table", "demo"]) == 0
    assert json.loads(capsys.readouterr().out)["changed"] is False
    assert readme(item_repo).read_text(encoding="utf-8") == text


@pytest.mark.parametrize(
    "text",
    [
        "# Demo\n\nsem marcadores\n",
        "# Demo\n<!-- ws:items -->\n",
        "# Demo\n<!-- /ws:items -->\n",
        "# Demo\n<!-- /ws:items -->\n<!-- ws:items -->\n",
    ],
)
def test_table_without_markers_exits_1(item_repo, capsys, text):
    readme(item_repo).write_text(text, encoding="utf-8")

    code = main(["item", "table", "demo"])

    assert code == 1
    assert readme(item_repo).read_text(encoding="utf-8") == text
    assert "ws:items" in capsys.readouterr().err


def test_load_project_without_project_toml_is_missing(item_repo):
    (item_repo / "projects" / "demo" / "project.toml").unlink()

    with pytest.raises(ProjectMissing):
        items.load_project(item_repo, "demo")
    assert items.project_slugs(item_repo) == []


def test_a_new_project_from_the_template_is_checkable_and_its_table_is_stable(item_repo, capsys):
    import shutil
    from datetime import date

    from ws.project import new_project

    shutil.copytree(TEMPLATES.parent / "project", item_repo / "templates" / "project")
    new_project("fresh", item_repo, date(2026, 11, 13))

    assert check(capsys, "fresh")[0] == 0
    assert main(["item", "table", "fresh"]) == 0
    assert json.loads(capsys.readouterr().out)["changed"] is False
