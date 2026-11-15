import json
from datetime import date
from pathlib import Path

import pytest
from test_card import (
    NOW,
    START_FIELD,
    approve,
    claude_settings,  # noqa: F401
    create_draft,
    make_draft,
    pending_files,
    preview,
    world,  # noqa: F401
)

from ws import card
from ws.config import data_dir

GOLDEN = Path(__file__).parent / "golden"
FIXED_SITE = "https://example.atlassian.net"
ISSUE_LINK = ("POST", "/rest/api/3/issueLink")
COMMENT_BODY = "Passos:\n\n- um\n- dois\n\n```python\nprint(1)\n```\n"

DRAFTS = {
    "create": lambda name: create_draft(name),
    "create-epic": lambda name: create_draft(
        name, title="[FRONT] Épico novo", type="epic", epic=None, sprint=None
    ),
    "edit": lambda name: make_draft(
        name, "edit", key="TS-101", priority="High", due=date(2026, 11, 12)
    ),
    "move": lambda name: make_draft(name, "move", key="TS-101", to="Em Andamento"),
    "comment": lambda name: make_draft(name, "comment", COMMENT_BODY, key="TS-101"),
    "worklog": lambda name: make_draft(
        name, "worklog", "Revisão.\n", key="TS-101", time="1h 30m", day=date(2026, 10, 26)
    ),
    "link": lambda name: make_draft(
        name, "link", key="TS-101", blocks=["TS-120"], relates=["TS-102"]
    ),
}

CODES = {
    "create": "68ca2eaca01d",
    "create-epic": "f3cc753e1952",
    "edit": "e43169158448",
    "move": "86dec154f2c1",
    "comment": "688f6dad3216",
    "worklog": "ce869cf509e4",
    "link": "7f9ff9787aed",
    "batch": "5e9a18f059bf",
}


def prepare(world, ops):  # noqa: F811
    world.set_card("TS-101", **{START_FIELD: None})
    world.fake.routes[ISSUE_LINK] = (201, "")
    for number, op in enumerate(ops, 1):
        DRAFTS[op](f"{number}-{op}.md")
    return data_dir() / "cards" / "drafts"


def normalise(text, world, drafts):  # noqa: F811
    return text.replace(str(drafts), "<drafts>").replace(world.fake.site, FIXED_SITE)


def previewed(world, capsys, ops):  # noqa: F811
    drafts = prepare(world, ops)
    out, code = preview(drafts, capsys)
    [record] = pending_files()
    saved = json.loads(record.read_text())
    return drafts, out, code, saved


def fixed_site_code(saved):
    return card.approval_code(FIXED_SITE, saved["requests"], saved["before"], saved["summary"])


@pytest.mark.parametrize("op", [*DRAFTS, "batch"])
def test_golden_codes_per_operation(world, capsys, op):  # noqa: F811
    ops = list(DRAFTS) if op == "batch" else [op]

    _, _, code, saved = previewed(world, capsys, ops)

    assert code == card.approval_code(
        saved["site"], saved["requests"], saved["before"], saved["summary"]
    )
    assert fixed_site_code(saved) == CODES[op]


def test_golden_pending_record(world, capsys):  # noqa: F811
    drafts, _, _, saved = previewed(world, capsys, list(DRAFTS))

    assert list(saved) == [
        "code",
        "created_at",
        "site",
        "today",
        "sid",
        "drafts",
        "requests",
        "before",
        "summary",
    ]
    assert saved["created_at"] == NOW.isoformat()
    assert [item["path"] for item in saved["drafts"]] == [
        f"{drafts}/{number}-{op}.md" for number, op in enumerate(DRAFTS, 1)
    ]
    kept = {key: saved[key] for key in ("site", "today", "requests", "before", "summary")}
    text = normalise(json.dumps(kept, ensure_ascii=False, indent=2), world, drafts)
    assert json.loads(text) == json.loads((GOLDEN / "card-pending.json").read_text("utf-8"))


def test_golden_preview_text(world, capsys):  # noqa: F811
    drafts, out, code, _ = previewed(world, capsys, list(DRAFTS))

    text = normalise(out, world, drafts).replace(code, "<code>")

    assert text == (GOLDEN / "card-preview.txt").read_text("utf-8")


APPLY_REPORT = (
    "Criado: 1-create.md https://example.atlassian.net/browse/TS-200\n"
    "Criado: 2-create-epic.md https://example.atlassian.net/browse/TS-200\n"
    "Aplicado: 3-edit.md https://example.atlassian.net/browse/TS-101\n"
    "Aplicado: 4-move.md https://example.atlassian.net/browse/TS-101\n"
    "Aplicado: 5-comment.md https://example.atlassian.net/browse/TS-101\n"
    "Aplicado: 6-worklog.md https://example.atlassian.net/browse/TS-101\n"
    "Vinculado: TS-101 bloqueia TS-120\n"
    "Vinculado: TS-101 relaciona-se com TS-102\n"
)
APPLY_WRITES = [
    ("POST", "/rest/api/3/issue"),
    ("POST", "/rest/api/3/issue"),
    ("PUT", "/rest/api/3/issue/TS-101"),
    ("POST", "/rest/api/3/issue/TS-101/transitions"),
    ("PUT", "/rest/api/3/issue/TS-101"),
    ("POST", "/rest/api/3/issue/TS-101/comment"),
    ("POST", "/rest/api/3/issue/TS-101/worklog"),
    ("POST", "/rest/api/3/issueLink"),
    ("POST", "/rest/api/3/issueLink"),
]


def test_golden_apply_report(world, capsys):  # noqa: F811
    drafts, _, code, _ = previewed(world, capsys, list(DRAFTS))
    capsys.readouterr()

    assert approve(drafts, code) == 0

    out = capsys.readouterr()
    assert out.err == ""
    assert normalise(out.out, world, drafts) == APPLY_REPORT
    writes = world.writes()
    assert [(r["method"], r["path"]) for r in writes] == APPLY_WRITES
    pinned = json.loads((GOLDEN / "card-pending.json").read_text("utf-8"))["requests"]
    assert [r["body"] for r in writes] == [r["body"] for r in pinned]
