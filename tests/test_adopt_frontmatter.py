import tomllib

import pytest
from adopt_items import frontmatter as fm

FIELDS = {"type": "task", "card": "TS-1", "assignee": "dev-aaaaaaaaaa"}

BODIES = {
    "lf": "# Title\n\ntext\n",
    "crlf": "# Title\r\n\r\ntext\r\n",
    "no_final_newline": "# Title\n\ntext",
    "bom": "﻿# Title\n\ntext\n",
    "plus_line": "# Title\n+++\nnot a block\n+++\n",
    "empty": "",
}


@pytest.mark.parametrize("original", BODIES.values(), ids=BODIES.keys())
def test_insert_keeps_the_body_byte_for_byte(original):
    result = fm.insert_front_matter(original, FIELDS)
    assert result.endswith(original)
    block = result[: len(result) - len(original)]
    assert block.startswith("+++\n") and block.endswith("+++\n")
    assert tomllib.loads(block[4:-4])["card"] == "TS-1"


def test_insert_refuses_a_file_that_already_has_front_matter():
    text = '+++\ncard = "TS-1"\n+++\n# x\n'
    with pytest.raises(ValueError):
        fm.insert_front_matter(text, FIELDS)


@pytest.mark.parametrize(
    "text", ["+++ not matter\n+++\n", "---\na: 1\n---\n", "# x\n+++\n+++\n", "+++\nno close\n"]
)
def test_has_front_matter_is_false_for_a_horizontal_rule_start(text):
    assert fm.has_front_matter(text) is False


def test_has_front_matter_true_and_crlf():
    assert fm.has_front_matter("+++\na = 1\n+++\nbody")
    assert fm.has_front_matter("+++\r\na = 1\r\n+++\r\nbody")


def test_dump_fields_order_and_types():
    fields = {"type": "task", "card": "TS-1", "blocks": ["TS-2"], "docs": []}
    out = fm.dump_fields(fields)
    assert out.splitlines()[0] == 'card = "TS-1"'
    assert "docs" not in out
    assert 'blocks = ["TS-2"]' in out
    assert tomllib.loads(out) == {"card": "TS-1", "type": "task", "blocks": ["TS-2"]}


def test_dump_fields_all_keys_in_order():
    fields = {
        "docs": ["a.md"],
        "relates": ["TS-5"],
        "blocked_by": ["TS-4", "tasks/1-x.md"],
        "blocks": ["TS-3"],
        "reporter": "r",
        "assignee": "a",
        "epic": "TS-9",
        "type": "bug",
        "card": "TS-1",
    }
    keys = [line.split(" = ")[0] for line in fm.dump_fields(fields).splitlines()]
    assert keys == [
        "card",
        "type",
        "epic",
        "assignee",
        "reporter",
        "blocks",
        "blocked_by",
        "relates",
        "docs",
    ]


def test_dump_fields_tracker_false():
    out = fm.dump_fields({"tracker": False, "status": "done"})
    assert "tracker = false" in out
    assert 'status = "done"' in out
    assert "[tracker]" not in out
    assert tomllib.loads(out) == {"tracker": False, "status": "done"}


def test_dump_fields_escapes_quotes():
    out = fm.dump_fields({"card": 'a"b\\c'})
    assert tomllib.loads(out) == {"card": 'a"b\\c'}


def test_replace_front_matter_keeps_the_body():
    body = "# Title\r\n+++\r\ntext"
    text = '+++\ncard = "TS-1"\n+++\n' + body
    out = fm.replace_front_matter(text, {"card": "TS-2", "type": "bug"})
    assert out.endswith(body)
    assert 'card = "TS-2"' in out
    assert 'card = "TS-1"' not in out


def test_replace_front_matter_without_block_raises():
    with pytest.raises(ValueError):
        fm.replace_front_matter("# x\n", FIELDS)


TEMPLATE = "# T\n\n## Contexto\n\n## Pronto quando\n\n## Outro\n"


def test_fill_sections_inserts_under_the_headings():
    out = fm.fill_sections(TEMPLATE, "the scope", "the done")
    assert out == "# T\n\n## Contexto\n\nthe scope\n\n## Pronto quando\n\nthe done\n\n## Outro\n"


def test_fill_sections_appends_missing_headings():
    out = fm.fill_sections("# T\n\ntext", "the scope", "the done")
    assert out == "# T\n\ntext\n\n## Contexto\n\nthe scope\n\n## Pronto quando\n\nthe done\n"


def test_fill_sections_without_text_is_a_no_op():
    assert fm.fill_sections(TEMPLATE, None, None) == TEMPLATE
    assert fm.fill_sections("# T", "", None) == "# T"


def test_fill_sections_keeps_crlf():
    out = fm.fill_sections("## Contexto\r\n\r\nx\r\n", "s", None)
    assert out == "## Contexto\r\n\r\ns\r\n\r\nx\r\n"
