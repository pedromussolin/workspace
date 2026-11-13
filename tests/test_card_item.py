import pytest
from test_card import (
    EMAIL,
    approve,
    claude_settings,  # noqa: F401
    create_draft,
    make_draft,
    pending_files,
    preview,
    problems,
    world,  # noqa: F401
)

from ws import card, itemrecord
from ws.config import data_dir
from ws.identity import dev_id

REL = "projects/demo/tasks/01-a.md"
OTHER = "projects/demo/tasks/02-b.md"


def item_text(extra=""):
    own = dev_id(EMAIL)
    return (
        "+++\n"
        "# kept comment\n"
        'type = "task"\n'
        'epic = "TS-100"\n'
        f'assignee = "{own}"\n'
        f'reporter = "{own}"\n'
        f"{extra}"
        "+++\n"
        "# Fazer a coisa\n\nTexto.\n"
    )


@pytest.fixture
def repo(tmp_path, monkeypatch, world):  # noqa: F811
    root = tmp_path / "repo"
    (root / "projects" / "demo" / "tasks").mkdir(parents=True)
    monkeypatch.setenv("WS_REPO_ROOT", str(root))
    (root / REL).write_text(item_text(), encoding="utf-8")
    return root


def created_lines():
    log = data_dir() / "cards" / "created.tsv"
    return log.read_text(encoding="utf-8").splitlines() if log.exists() else []


def test_draft_item_key_shape(world, capsys):  # noqa: F811
    assert "item must be a path like projects/<slug>/tasks/NN-name.md" in problems(
        create_draft(item="../x.md"), capsys
    )
    assert "item is only for a card; an epic or an initiative has no item" in problems(
        create_draft(type="epic", epic=None, sprint=None, item=REL), capsys
    )


def test_create_with_item_writes_the_card_back(repo, capsys):
    original = (repo / REL).read_text(encoding="utf-8")
    path = create_draft(item=REL)
    _, code = preview(path, capsys)
    capsys.readouterr()

    assert approve(path, code) == 0

    assert (repo / REL).read_text(encoding="utf-8") == original.replace(
        "+++\n", '+++\ncard = "TS-200"\n', 1
    )
    assert f'Item atualizado: {REL} (card = "TS-200")' in capsys.readouterr().out
    assert any(line.split("\t")[1] == "TS-200" for line in created_lines())
    assert itemrecord.recorded(REL) is None


def test_create_for_an_item_with_a_card_is_refused(repo, world, capsys):  # noqa: F811
    (repo / REL).write_text(item_text('card = "TS-5"\n'), encoding="utf-8")

    text = problems(create_draft(item=REL), capsys)

    assert f"item {REL} already has card TS-5: a second create would duplicate it" in text


def test_create_whose_fields_differ_from_the_item_is_refused(repo, world, capsys):  # noqa: F811
    text = problems(create_draft(item=REL, type="improvement"), capsys)

    assert f"type differs from the item {REL} (task)" in text


def test_create_for_a_missing_or_untracked_item_is_refused(repo, world, capsys):  # noqa: F811
    assert f"item {OTHER} is not an item" in problems(create_draft(item=OTHER), capsys)
    (repo / REL).write_text(item_text("tracker = false\n"), encoding="utf-8")
    assert f"item {REL} has tracker = false" in problems(create_draft(item=REL), capsys)


def test_two_creates_for_one_item_are_refused(repo, world, capsys):  # noqa: F811
    create_draft("a.md", item=REL)
    create_draft("b.md", item=REL)
    folder = data_dir() / "cards" / "drafts"

    assert card.run_preview(str(folder)) == 1

    out = capsys.readouterr().out
    assert out.count(f"two drafts create a card for item {REL}") == 2
    assert world.writes() == []


def test_create_for_a_recorded_item_is_refused(repo, world, capsys):  # noqa: F811
    itemrecord.record(REL, "?")

    text = problems(create_draft(item=REL), capsys)

    assert (
        f"item {REL} has an uncertain create (?): check the tracker, then run ws item set-card "
        f"{REL} <ref> (or --none)"
    ) in text


def test_write_back_failure_records_and_finishes_the_batch(repo, world, capsys):  # noqa: F811
    create_draft("a-create.md", item=REL)
    make_draft("b-edit.md", "edit", key="TS-101", priority="High")
    folder = data_dir() / "cards" / "drafts"
    _, code = preview(folder, capsys)
    capsys.readouterr()
    original = card._send

    def breaking(client, request):
        reply = original(client, request)
        if request["path"] == "/rest/api/3/issue":
            (repo / REL).write_text("+++\ntype = \n+++\n", encoding="utf-8")
        return reply

    card._send = breaking
    try:
        assert approve(folder, code) == 1
    finally:
        card._send = original

    out = capsys.readouterr().out
    assert (repo / REL).read_text(encoding="utf-8") == "+++\ntype = \n+++\n"
    assert "TS-200" in out and REL in out and f"ws item set-card {REL} TS-200" in out
    assert len(world.writes()) == 2
    assert itemrecord.recorded(REL) == "TS-200"
    assert pending_files() == []


def test_uncertain_create_records_the_item(repo, world, capsys):  # noqa: F811
    world.fake.routes[("POST", "/rest/api/3/issue")] = (502, "{}")
    path = create_draft(item=REL)
    _, code = preview(path, capsys)
    capsys.readouterr()

    assert approve(path, code) == 3

    assert itemrecord.recorded(REL) == "?"


def test_record_replaces_and_clears(tmp_path, world):  # noqa: F811
    itemrecord.record(REL, "?")
    itemrecord.record(OTHER, "TS-7")
    itemrecord.record(REL, "TS-9")

    assert (itemrecord.recorded(REL), itemrecord.recorded(OTHER)) == ("TS-9", "TS-7")
    itemrecord.clear(REL)
    assert itemrecord.recorded(REL) is None
    assert itemrecord.recorded(OTHER) == "TS-7"
