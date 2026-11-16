import json
from pathlib import Path

import pytest
from test_card import (
    approve,
    claude_settings,  # noqa: F401
    create_draft,
    make_draft,
    pending_files,
    preview,
    world,  # noqa: F401
)

from ws import card
from ws.cli import main
from ws.config import data_dir
from ws.tracker import write


def json_twin(md_path, name, **changes):
    document = {**card.show(str(md_path)), **changes}
    path = md_path.parent / name
    path.write_text(json.dumps(document, ensure_ascii=False, indent=2), encoding="utf-8")
    return path


def record_without_sources(path):
    """The pending record minus the sources, code, summary and session."""
    record = json.loads(path.read_text(encoding="utf-8"))
    for name in ("drafts", "code", "summary", "sid"):
        record.pop(name)
    return record


def summary_of(path):
    return json.loads(path.read_text(encoding="utf-8"))["summary"]


def test_json_draft_previews_like_its_markdown_twin(world, capsys):  # noqa: F811
    md = create_draft("twin.md")
    js = json_twin(md, "twin.json")

    md_out, md_code = preview(md, capsys)
    [md_record] = pending_files()
    md_record_data = record_without_sources(md_record)
    md_sources = json.loads(md_record.read_text(encoding="utf-8"))["drafts"]
    md_summary = summary_of(md_record)
    md_record.unlink()
    js_out, js_code = preview(js, capsys)
    [js_record] = pending_files()
    js_sources = json.loads(js_record.read_text(encoding="utf-8"))["drafts"]

    # The code covers the summary, whose header names the file, so only the extension differs.
    assert md_code != js_code
    assert [line.replace("twin.md", "twin.json") for line in md_summary] == summary_of(js_record)
    assert md_out.replace("twin.md", "twin.json").replace(md_code, js_code) == js_out
    assert md_record_data == record_without_sources(js_record)
    assert md_sources[0]["sha256"] != js_sources[0]["sha256"]
    assert js_sources[0]["path"] == str(js)


def test_json_draft_applies_after_its_preview(world, capsys):  # noqa: F811
    js = json_twin(create_draft("go.md"), "go.json")
    _, code = preview(js, capsys)

    assert approve(js, code) == 0
    assert world.writes()


def test_json_draft_with_an_unknown_key_is_refused(world, capsys):  # noqa: F811
    js = json_twin(create_draft("odd.md"), "odd.json", surprise="x")

    assert main(["card", "check", str(js)]) == 1
    verdict = json.loads(capsys.readouterr().out)
    assert verdict["ok"] is False
    assert any("surprise" in line for line in verdict["problems"])


def test_a_malformed_json_draft_is_refused(world, capsys):  # noqa: F811
    path = make_draft("bad.md", "move", key="TS-1", to="x").with_name("bad.json")
    path.write_text("{not json", encoding="utf-8")

    assert main(["card", "check", str(path)]) == 1
    assert "JSON" in capsys.readouterr().out


def test_check_validates_a_card_plan_document(world, capsys):  # noqa: F811
    md = create_draft("plan.md")
    preview(md, capsys)
    plan = card.preview_plan(str(md))
    good = md.parent / "plan.json"
    good.write_text(json.dumps(plan), encoding="utf-8")
    assert main(["card", "check", str(good)]) == 0
    assert json.loads(capsys.readouterr().out)["ok"] is True

    plan["steps"] = "nope"
    bad = md.parent / "bad-plan.json"
    bad.write_text(json.dumps(plan), encoding="utf-8")
    assert main(["card", "check", str(bad)]) == 1
    assert json.loads(capsys.readouterr().out)["ok"] is False


def test_a_folder_mixes_md_and_json_drafts(world, capsys):  # noqa: F811
    folder = data_dir() / "cards" / "drafts" / "mix"
    folder.mkdir(parents=True)
    md = make_draft("mix/one.md", "move", key="TS-101", to="Em Andamento")
    json_twin(md, "two.json", to="Em Validação")

    assert [p.name for p in card.collect(str(folder))] == ["one.md", "two.json"]
    out, _ = preview(folder, capsys)
    assert "(one.md)" in out and "(two.json)" in out


def test_write_and_remove_accept_json_names(world):  # noqa: F811
    path = card.write_draft("made.json", "{}")

    assert path.name == "made.json"
    assert card.remove_draft("made.json") is True


SCHEMA_HAS_STATUS = "status" in json.dumps(
    json.loads((Path(card.__file__).parent / "data/contracts/card-write.schema.json").read_text())
)


@pytest.mark.skipif(not SCHEMA_HAS_STATUS, reason="card-write schema has no `status` yet")
def test_json_move_takes_a_neutral_status(world, capsys):  # noqa: F811
    md = make_draft("m.md", "move", key="TS-101", to="Em Andamento")
    document = {"$schema": "card-write", "version": 1, "op": "move", "key": "TS-101"}
    path = md.with_name("m.json")
    path.write_text(json.dumps({**document, "status": "in_progress"}), encoding="utf-8")

    assert main(["card", "check", str(path)]) == 0
    assert json.loads(capsys.readouterr().out)["ok"] is True


MOVE = {"$schema": "card-write", "version": 1, "op": "move", "key": "TS-101"}


def test_move_with_neither_to_nor_status_is_refused():
    assert write.check_document(MOVE) == ["missing key 'to' for op move"]


@pytest.mark.skipif(not SCHEMA_HAS_STATUS, reason="card-write schema has no `status` yet")
def test_move_with_both_to_and_status_is_refused():
    both = write.check_document({**MOVE, "to": "x", "status": "done"})

    assert both == ["a move needs exactly one of to or status, not both"]
