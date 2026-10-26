"""The common-word dictionaries in the new-word check: they clear a word only at a sentence start.

The fake dictionaries of `conftest.py` hold `gadget` and `sprocket` (English) and `engrenagem` and
`parafuso` (Portuguese); `Zorblax` and `Quuxmark` are in neither.
"""

import pytest

from ws import dictionary
from ws.newwords import (
    NewWord,
    Place,
    at_sentence_start,
    check_message,
    check_range,
    check_staged,
    format_report,
    word_spans,
    words_of,
)


def commit(repo, git, message, files=None):
    for name, content in (files or {}).items():
        (repo / name).write_text(content, encoding="utf-8")
        git(repo, "add", name)
    git(repo, "commit", "-q", "--allow-empty", "-m", message)


def new_in_last_commit(repo, table):
    return check_range(repo, ["HEAD~1..HEAD"], table, "HEAD~1")


def found_in(repo, git, table, text):
    """The new words, as (word, line) pairs, of a note added on top of a commit that knows none."""
    commit(repo, git, "base", {"a.md": "fine\n"})
    commit(repo, git, "two", {"a.md": f"fine\n{text}\n"})
    return [
        (item.word, [place.line for place in item.places])
        for item in new_in_last_commit(repo, table)
    ]


def test_spans_give_each_word_its_column_and_camel_case_parts_keep_theirs():
    assert list(word_spans("ab Zorblax, HTTPServer x_Frobnitz")) == [
        ("Zorblax", 3),
        ("HTTP", 12),
        ("Server", 16),
        ("Frobnitz", 25),
    ]
    assert [word for word, _ in word_spans("ACME_API acmeCorp")] == list(
        words_of("ACME_API acmeCorp")
    )


def test_a_decomposed_accent_does_not_shift_the_columns():
    assert list(word_spans("Méridia Zorblax")) == [("Méridia", 0), ("Zorblax", 8)]


@pytest.mark.parametrize(
    "before",
    [
        "",
        "   ",
        "> ",
        ">> ",
        "## ",
        "- ",
        "  * ",
        "+ ",
        "1. ",
        "12) ",
        "- 3. ",
        "| ",
        "| uno | ",
        "**",
        "- **",
        "_",
        "`",
        '"',
        "'",
        "(",
        "[",
        '> ("',
        "Done. ",
        "Done.",
        "Feito: ",
        "Wow! ",
        "Why? ",
        "Ok.  **",
        "see x.y: (",
    ],
)
def test_text_that_leaves_a_word_at_the_start_of_a_sentence(before):
    assert at_sentence_start(before)


@pytest.mark.parametrize(
    "before",
    [
        "talk with ",
        "the ",
        "a, ",
        "- [ ] ",
        "x ",
        "Zorblax_",
        "2",
        "see e.g",
        "foo-",
        "a;",
        "a) b ",
    ],
)
def test_text_that_leaves_a_word_in_the_middle_of_a_sentence(before):
    assert not at_sentence_start(before)


@pytest.mark.parametrize(
    "line",
    [
        "Gadget came first",
        "  Gadget came first",
        "## Gadget",
        "- Gadget",
        "3. Gadget",
        "> Gadget",
        "| Gadget | Sprocket |",
        "Sprocket works. Gadget",
        "Engrenagem: Gadget",
        "**Gadget** works",
        "GADGET",
        "Parafuso works: Sprocket",
    ],
)
def test_the_dictionary_clears_a_word_at_the_start_of_a_sentence(repo, git, table, line):
    assert found_in(repo, git, table, line) == []


@pytest.mark.parametrize(
    "line",
    [
        "talk with Gadget",
        "the Gadget works",
        "see Gadget.",
        "- [ ] Gadget",
        "ZorblaxGadget",
        "ACME_Gadget",
    ],
)
def test_the_dictionary_does_not_clear_a_word_in_the_middle_of_a_sentence(repo, git, table, line):
    assert [word for word, _ in found_in(repo, git, table, line)] != []
    assert any(word in {"Gadget", "GADGET"} for word, _ in found_in(repo, git, table, line))


def test_a_word_cleared_in_one_place_is_reported_where_it_is_mid_sentence(repo, git, table):
    text = "Gadget works\nthe team likes the Gadget\nGadget again"
    assert found_in(repo, git, table, text) == [("Gadget", [3])]


def test_the_dictionary_ignores_accents_and_case(repo, git, table):
    assert found_in(repo, git, table, "Engrenagem\nPARAFUSO\nÉngrenagem") == []


def test_a_word_the_dictionary_does_not_have_is_reported_at_a_sentence_start(repo, git, table):
    assert found_in(repo, git, table, "Zorblax is new") == [("Zorblax", [2])]


def test_a_commit_message_follows_the_same_rule(repo, git, table):
    commit(repo, git, "base", {"a.md": "fine\n"})
    text = "feat: Gadget novo\n\nGadget usa o Sprocket.\nEngrenagem: Parafuso"
    found = check_message(repo, text, table, "HEAD")
    assert [(item.word, [place.line for place in item.places]) for item in found] == [
        ("Sprocket", [3])
    ]


def test_the_staged_check_uses_the_dictionary_too(repo, git, table):
    commit(repo, git, "base", {"a.md": "fine\n"})
    (repo / "a.md").write_text("fine\nGadget here\nand Sprocket there\n", encoding="utf-8")
    git(repo, "add", "a.md")
    found = check_staged(repo, table, "HEAD")
    assert [(item.word, str(item.places[0])) for item in found] == [("Sprocket", "a.md:3")]


def test_without_the_dictionaries_a_sentence_start_word_is_reported(
    repo, git, table, ws_dictionaries
):
    for path in ws_dictionaries.iterdir():
        path.unlink()
    assert found_in(repo, git, table, "Gadget works") == [("Gadget", [2])]


def test_the_report_adds_one_line_when_the_dictionaries_are_missing(ws_dictionaries):
    word = NewWord("Zorblax", (Place("a.md", 1),))
    assert format_report([word], blocking=True, missing=dictionary.missing()) == format_report(
        [word], blocking=True
    )
    (ws_dictionaries / "brazilian").unlink()
    with_note = format_report([word], blocking=True, missing=dictionary.missing())
    plain = format_report([word], blocking=True)
    assert len(with_note) == len(plain) + 1
    note = next(line for line in with_note if line not in plain)
    assert "wbrazilian" in note
    assert "wamerican" not in note
    assert "`ws setup` installs them" in note
