import os
import stat
from datetime import date

import pytest

from ws import itemfile
from ws.itemfile import Item, ItemError
from ws.tracker.vocab import REF

ME = "dev-0123456789"
ANA = "dev-abcdef0123"

EXAMPLE = f"""+++
card = "TS-5570"
type = "feature"
epic = "TS-5278"
assignee = "{ME}"
reporter = "{ME}"
blocks = ["TS-5701"]
blocked_by = ["TS-5569", "tasks/13-plan-ts-5567.md"]
relates = []
docs = ["13-plan-ts-5570.md", "13-closing-design.md"]

[tracker]
status = "todo"
priority = "Medium"
due = 2026-11-20
sprint = ""
synced = 2026-11-13
+++
# 13 — Fechamento automático

free text
"""


def write(tmp_path, text, name="01-a.md"):
    path = tmp_path / name
    path.write_text(text, encoding="utf-8")
    return path


def item_of(tmp_path, front: str) -> Item:
    item = itemfile.read_item(write(tmp_path, f"+++\n{front}+++\n# t\n"))
    assert item is not None
    return item


def valid(extra="", drop=()):
    keys = {
        "type": 'type = "task"\n',
        "assignee": f'assignee = "{ME}"\n',
        "reporter": f'reporter = "{ANA}"\n',
    }
    return "".join(v for k, v in keys.items() if k not in drop) + extra


def problems(tmp_path, front):
    return itemfile.schema_problems(item_of(tmp_path, front))


def test_ref_matches_card_refs():
    assert REF.fullmatch("TS-5570")
    assert not REF.fullmatch("ts 1")
    assert not REF.fullmatch("TS-0")


def test_a_file_without_front_matter_is_a_document(tmp_path):
    assert itemfile.read_item(write(tmp_path, "# Plan\n\ntext\n")) is None


def test_reads_the_contract_fields(tmp_path):
    item = itemfile.read_item(write(tmp_path, EXAMPLE))
    assert item.card == "TS-5570"
    assert item.tracked
    assert item.links["blocked_by"] == ["TS-5569", "tasks/13-plan-ts-5567.md"]
    assert item.links["relates"] == []
    assert item.cache["due"] == date(2026, 11, 20)
    assert item.heading == "13 — Fechamento automático"
    assert itemfile.schema_problems(item) == []


def test_read_errors(tmp_path):
    bad = tmp_path / "bad.md"
    bad.write_bytes(b"+++\ncard = \xff\n+++\n")
    with pytest.raises(ItemError):
        itemfile.read_item(bad)
    with pytest.raises(ItemError):
        itemfile.read_item(write(tmp_path, '+++\ncard = "TS-1"\n# no close\n'))
    with pytest.raises(ItemError):
        itemfile.read_item(write(tmp_path, "+++\ncard = \n+++\n"))


def test_untracked_and_empty_links(tmp_path):
    item = item_of(tmp_path, 'tracker = false\nstatus = "done"\n')
    assert not item.tracked
    assert item.cache == {}
    assert item.card is None
    assert item.links == {"blocks": [], "blocked_by": [], "relates": []}


def test_schema_refuses_unknown_keys(tmp_path):
    assert "unknown key 'title'" in problems(tmp_path, valid('title = "x"\n'))
    out = problems(tmp_path, valid('[tracker]\ncolour = "x"\n'))
    assert "unknown key 'colour' in [tracker]" in out


def test_schema_refuses_me(tmp_path):
    out = problems(tmp_path, valid().replace(ME, "me"))
    assert "assignee must be a dev id, not me: the repo is shared; ws people me prints yours" in out
    out = problems(tmp_path, valid().replace(ME, "dev-XYZ"))
    assert "assignee must be a dev id (dev- and 10 hex digits)" in out


def test_schema_type_is_a_card_type(tmp_path):
    out = problems(tmp_path, valid().replace('"task"', '"epic"'))
    assert "type must be one of task, bug, hotfix, improvement, feature" in out


def test_schema_requires_type_and_people(tmp_path):
    assert "missing key 'type'" in problems(tmp_path, valid(drop=("type",)))
    assert "missing key 'assignee'" in problems(tmp_path, valid(drop=("assignee",)))
    assert "missing key 'reporter'" in problems(tmp_path, valid(drop=("reporter",)))


def test_schema_epic_is_required_only_with_a_card(tmp_path):
    assert "missing key 'epic'" in problems(tmp_path, valid('card = "TS-5"\n'))
    assert problems(tmp_path, valid()) == []
    assert problems(tmp_path, valid('card = "TS-5"\nepic = "TS-1"\n')) == []


def test_schema_card_and_links_are_refs_or_paths(tmp_path):
    assert "card must be a card ref" in problems(tmp_path, valid('card = "ts 1"\nepic = "TS-1"\n'))
    out = problems(tmp_path, valid('blocks = ["x.md"]\n'))
    assert (
        "blocks: 'x.md' is neither a card ref nor tasks/<file>.md nor ../<project>/tasks/<file>.md"
        in out
    )
    assert problems(tmp_path, valid('blocks = ["../other/tasks/02-x.md"]\n')) == []
    assert problems(tmp_path, valid('relates = ["TS-4", "tasks/01-a.md"]\n')) == []
    assert "blocks must be a list" in problems(tmp_path, valid('blocks = "TS-1"\n'))


def test_tracker_false_needs_a_status_and_no_card(tmp_path):
    assert "tracker = false needs a status" in problems(tmp_path, "tracker = false\n")
    out = problems(tmp_path, 'tracker = false\nstatus = "done"\ncard = "TS-1"\n')
    assert "tracker = false has no card" in out
    out = problems(tmp_path, 'tracker = false\nstatus = "doing"\n')
    assert any(p.startswith("status must be one of todo, in_progress, ") for p in out)
    assert problems(tmp_path, 'tracker = false\nstatus = "done"\n') == []
    out = problems(tmp_path, "tracker = true\n" + valid())
    assert "tracker is either false or the [tracker] table" in out


def test_a_broken_tracker_table(tmp_path):
    out = problems(tmp_path, valid('[tracker]\ndue = "soon"\n'))
    assert "[tracker] due must be a date" in out


FRONT = """+++
# a comment
type = "task"
assignee = "dev-0123456789"
blocks = [
  "TS-1",
]  # x
reporter = "dev-abcdef0123"

[tracker]
status = "todo"  # keep
+++
# t

body
"""


def test_set_keys_inserts_card_as_the_first_key():
    out = itemfile.set_keys(FRONT, {"card": "TS-9"})
    assert out == FRONT.replace("+++\n", '+++\ncard = "TS-9"\n', 1)


def test_set_keys_replaces_a_multiline_list():
    out = itemfile.set_keys(FRONT, {"blocks": ["TS-2"]})
    old, new = FRONT.splitlines(), out.splitlines()
    assert 'blocks = ["TS-2"]' in new
    assert [x for x in old if x not in ("blocks = [", '  "TS-1",', "]  # x")] == [
        x for x in new if x != 'blocks = ["TS-2"]'
    ]
    assert new.index('blocks = ["TS-2"]') == old.index("blocks = [")


def test_set_keys_replaces_a_scalar_and_keeps_crlf():
    text = FRONT.replace("\n", "\r\n")
    out = itemfile.set_keys(text, {"type": "bug"})
    assert out == text.replace('type = "task"', 'type = "bug"')


def test_set_keys_refuses_a_broken_front_matter():
    with pytest.raises(ItemError):
        itemfile.set_keys("+++\ncard = \n+++\n", {"card": "TS-1"})
    with pytest.raises(ItemError):
        itemfile.set_keys("no front matter\n", {"card": "TS-1"})


def test_set_cache_rewrites_only_the_table():
    out = itemfile.set_cache(
        FRONT, {"synced": date(2026, 11, 13), "status": "done", "priority": "High"}
    )
    assert out == FRONT.replace(
        'status = "todo"  # keep\n',
        'status = "done"\npriority = "High"\nsynced = 2026-11-13\n',
    )


def test_set_cache_keeps_the_blank_line_before_the_next_header():
    text = '+++\n[tracker]\nstatus = "todo"\n\n[other]\nx = 1\n+++\nbody\n'
    out = itemfile.set_cache(text, {"status": "done"})
    assert out == text.replace('"todo"', '"done"')


def test_set_cache_appends_a_missing_table():
    text = '+++\ntype = "task"\n+++\nbody\n'
    out = itemfile.set_cache(text, {"status": "todo", "due": date(2026, 1, 2)})
    assert out == '+++\ntype = "task"\n\n[tracker]\nstatus = "todo"\ndue = 2026-01-02\n+++\nbody\n'


def test_set_cache_refuses_unknown_keys_and_broken_results():
    with pytest.raises(ItemError):
        itemfile.set_cache(FRONT, {"colour": "x"})
    with pytest.raises(ItemError):
        itemfile.set_cache("+++\ntracker = false\n+++\n", {"status": "todo"})


def test_item_path_refuses_what_is_not_an_item_path(tmp_path):
    tasks = tmp_path / "projects" / "a" / "tasks"
    tasks.mkdir(parents=True)
    (tasks / "x.md").write_text("x")
    assert itemfile.item_path(tmp_path, "projects/a/tasks/x.md") == tasks / "x.md"
    for bad in ("../x.md", "projects/a/notes/x.md", "/abs/x.md", "projects/a/tasks/sub/x.md"):
        with pytest.raises(ItemError):
            itemfile.item_path(tmp_path, bad)
    outside = tmp_path / "secret.md"
    outside.write_text("x")
    (tasks / "link.md").symlink_to(outside)
    with pytest.raises(ItemError):
        itemfile.item_path(tmp_path, "projects/a/tasks/link.md")


def test_link_path_resolves_across_projects_and_stays_in_projects(tmp_path):
    for slug in ("demo", "other"):
        (tmp_path / "projects" / slug / "tasks").mkdir(parents=True)
    root = tmp_path
    assert (
        itemfile.link_path(root, "demo", "../other/tasks/02-x.md")
        == root / "projects/other/tasks/02-x.md"
    )
    assert itemfile.link_path(root, "demo", "tasks/01-a.md") == root / "projects/demo/tasks/01-a.md"
    for bad in (
        "../../x/tasks/a.md",
        "../../../etc/passwd",
        "../other/notes/a.md",
        "../other/tasks/sub/a.md",
    ):
        with pytest.raises(ItemError):
            itemfile.link_path(root, "demo", bad)
    outside = tmp_path / "secret.md"
    outside.write_text("x")
    (root / "projects/other/tasks/s.md").symlink_to(outside)
    with pytest.raises(ItemError):
        itemfile.link_path(root, "demo", "../other/tasks/s.md")


@pytest.mark.parametrize("slug", ["Demo", "demo_x", "-demo", "demo-", "de--mo", "../demo", ""])
def test_link_path_refuses_a_slug_that_is_not_a_project_name(tmp_path, slug):
    with pytest.raises(ItemError, match="is not a project name"):
        itemfile.link_path(tmp_path, slug, "tasks/01-a.md")


def test_write_text_replaces_atomically_and_keeps_the_mode(tmp_path):
    path = write(tmp_path, "old")
    path.chmod(0o640)
    itemfile.write_text(path, "new — ü\n")
    assert path.read_text(encoding="utf-8") == "new — ü\n"
    assert stat.S_IMODE(os.stat(path).st_mode) == 0o640
    assert [p.name for p in tmp_path.iterdir()] == ["01-a.md"]


def test_docs_are_relative_paths_inside_the_project(tmp_path):
    ok = valid('docs = ["../decisions.md", ".plan.md", "sub/a.md"]\n')
    assert problems(tmp_path, ok) == []
    for bad in ("../../other/x.md", "/abs.md", "a\\\\b.md", ""):
        out = problems(tmp_path, valid(f'docs = ["{bad}"]\n'))
        assert any(p.startswith("docs:") for p in out), bad


def test_a_non_string_status_is_a_problem_not_a_crash(tmp_path):
    out = problems(tmp_path, 'tracker = false\nstatus = ["done"]\n')
    assert any(p.startswith("status must be one of") for p in out)
