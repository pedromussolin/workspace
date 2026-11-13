from pathlib import Path

import pytest
from adopt_items import maprows
from adopt_items.maprows import Link, Row

from ws.identity import dev_id

HEADER = [
    "project", "file", "card", "action", "type", "epic", "title",
    "assignee", "reporter", "links", "status", "scope", "done_when", "notes",
]  # fmt: skip


def line(**kw: str) -> str:
    base = dict.fromkeys(HEADER, "-")
    base.update(card="TS-1", action="manter", type="Tarefa", title="[X] T", status="a fazer")
    base.update(assignee="ana", reporter="ana", project="p")
    base.update(kw)
    return "\t".join(base[c] for c in HEADER)


def write(tmp_path: Path, name: str, *lines: str, header: list[str] | None = None) -> None:
    (tmp_path / name).write_text("\n".join(["\t".join(header or HEADER), *lines]) + "\n")


def row(**kw) -> Row:
    base = dict(
        source="a.tsv", line=2, project="p", file=None, origin_project=None, card="TS-1",
        action="manter", type_="task", epic=None, assignee="ana", reporter="ana", links=(),
        status="a fazer", scope="", heading="H", done_when="",
    )  # fmt: skip
    base.update(kw)
    return Row(**base)


def test_load_rows_reads_the_header_and_ignores_the_extra_column(tmp_path):
    header = HEADER[:12] + ["done_when", "estimate_ai_days", "notes"]
    cells = dict.fromkeys(header, "-")
    cells.update(card="TS-9", scope="the scope", done_when="the end", status="concluída (1/1)")
    cells.update(estimate_ai_days="3.5")
    write(tmp_path, "vm-screens.tsv", "\t".join(cells[c] for c in header), header=header)
    rows = maprows.load_rows(tmp_path)
    assert len(rows) == 1
    assert (rows[0].scope, rows[0].done_when, rows[0].status) == (
        "the scope", "the end", "concluída (1/1)",
    )  # fmt: skip


def test_dash_becomes_none_and_novo_gets_a_unique_id(tmp_path):
    write(
        tmp_path, "others.tsv",
        line(card="novo", epic="-", assignee="-"),
        line(card="TS-4"),
        line(card="novo"),
    )  # fmt: skip
    rows = maprows.load_rows(tmp_path)
    assert [r.card for r in rows] == ["novo-others-2", "TS-4", "novo-others-4"]
    assert rows[0].epic is None and rows[0].assignee is None and rows[0].file is None
    assert rows[0].line == 2 and rows[0].source == "others.tsv"


def test_file_suffix_names_the_origin_project(tmp_path):
    write(tmp_path, "a.tsv", line(file="tasks/13-x.md (artemis-v2)"), line(file="CONTINUE.md"))
    first, second = maprows.load_rows(tmp_path)
    assert (first.file, first.origin_project) == ("tasks/13-x.md", "artemis-v2")


def test_non_tasks_file_is_none(tmp_path):
    write(tmp_path, "a.tsv", line(file="CONTINUE.md"))
    (only,) = maprows.load_rows(tmp_path)
    assert only.file is None


def test_heading_drops_the_title_prefix(tmp_path):
    write(tmp_path, "a.tsv", line(title="[FRONT] Estrutura base"), line(title="Sem prefixo"))
    first, second = maprows.load_rows(tmp_path)
    assert (first.heading, second.heading) == ("Estrutura base", "Sem prefixo")


def test_epic_alias_and_project_dir(tmp_path):
    write(tmp_path, "a.tsv", line(epic="VM TELAS"), line(epic="TS-7"))
    first, second = maprows.load_rows(tmp_path)
    assert (first.epic, second.epic) == ("novo-E1", "TS-7")
    assert maprows.PROJECT_DIR == {"whitelabel": "whitelabel-restructure"}
    assert maprows.EPIC_ALIAS == {"VM TELAS": "novo-E1"}
    assert maprows.TYPE_NEUTRAL["Nova função"] == "feature"


def test_load_rows_maps_the_neutral_type(tmp_path):
    write(tmp_path, "a.tsv", line(type="Melhoria"), line(type="-"), line(type="História"))
    types = [r.type_ for r in maprows.load_rows(tmp_path)]
    assert types == ["improvement", None, "História"]


def test_load_rows_reads_the_files_in_sorted_order(tmp_path):
    write(tmp_path, "b.tsv", line(card="TS-2"))
    write(tmp_path, "a.tsv", line(card="TS-1"))
    assert [r.card for r in maprows.load_rows(tmp_path)] == ["TS-1", "TS-2"]


def test_parse_links_canonical():
    assert maprows.parse_links("blocks:novo-3;blocked_by:TS-5569") == (
        Link("blocks", "novo-3"),
        Link("blocked_by", "TS-5569"),
    )


def test_parse_links_legacy_text():
    assert maprows.parse_links("Relates TS-4366, TS-5044 (cards antigos)") == (
        Link("relates", "TS-4366"),
        Link("relates", "TS-5044"),
    )
    assert maprows.parse_links("Blocks TS-4356, TS-4357") == (
        Link("blocks", "TS-4356"),
        Link("blocks", "TS-4357"),
    )
    assert maprows.parse_links("-") == ()


def test_neutral_status_table():
    f = maprows.neutral_status
    assert f("concluída (29/10)") == "done"
    assert f("absorvida") == "cancelled"
    assert f("Cancelada") == "cancelled"
    assert f("em andamento (23/10)") == "in_progress"
    assert f("a fazer (mapeada para depois)") == "todo"
    assert f("Decisões pendentes") == "todo"
    assert f("adiada") == "todo"
    assert f("qualquer coisa") is None


def test_load_people_hashes_emails_and_accepts_dev_ids(tmp_path):
    path = tmp_path / "people.toml"
    path.write_text('ana = " Ana@Example.com "\nbob = "dev-0123456789"\ncy = "cy"\n')
    with pytest.raises(ValueError, match="cy"):
        maprows.load_people(path)
    path.write_text('ana = " Ana@Example.com "\nbob = "dev-0123456789"\n')
    people = maprows.load_people(path)
    assert people == {"ana": dev_id("ana@example.com"), "bob": "dev-0123456789"}


def test_check_rows_lists_every_problem():
    people = {"ana": "dev-0123456789"}
    rows = [
        row(line=2, action="perguntar"),
        row(line=3, card="TS-2", assignee="zed"),
        row(line=4, card="TS-3", type_="História"),
        row(line=5, card="-", action="sem-card", file="tasks/1-x.md", status="???"),
        row(line=6, card="novo-a-6", links=(Link("blocks", "novo-99"),)),
    ]
    problems = maprows.check_rows(rows, people)
    assert len(problems) == 5
    assert all(p.startswith("a.tsv:") for p in problems)
    assert [p.split(":")[1].split()[0] for p in problems] == ["2", "3", "4", "5", "6"]


def test_check_rows_requires_people_on_tracked_rows_only():
    people = {"ana": "dev-0123456789"}
    tracked = row(assignee=None)
    assert len(maprows.check_rows([tracked], people)) == 1
    free = row(card="-", action="sem-card", assignee=None, reporter=None, status="a fazer")
    assert maprows.check_rows([free], people) == []


def test_check_rows_refuses_a_pending_epic_with_an_existing_card():
    people = {"ana": "dev-0123456789"}
    assert len(maprows.check_rows([row(card="TS-5", epic="novo-E3")], people)) == 1
    assert maprows.check_rows([row(card="novo-a-2", epic="novo-E3")], people) == []
    assert maprows.check_rows([row(card="-", action="sem-card", epic="novo-E3")], people) == []


def test_check_rows_ignores_epico_rows():
    r = row(project="epico", assignee="nobody", reporter="nobody", type_="História")
    assert maprows.check_rows([r], {}) == []


@pytest.mark.parametrize("kind", ["Epic", "Iniciativa"])
def test_epic_and_initiative_rows_are_not_checked_as_items(kind, tmp_path):
    write(tmp_path, "a.tsv", line(type=kind, assignee="-"))
    assert maprows.check_rows(maprows.load_rows(tmp_path), {}) == []
