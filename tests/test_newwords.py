"""New-word detection: capitalized words that the pushed state, `.known-words` and the analogs
do not know."""

from pathlib import Path

import pytest

from ws import newwords
from ws.newwords import (
    KNOWN_WORDS_FILE,
    Place,
    add_known_words,
    check_message,
    check_range,
    check_staged,
    parse_known_words,
    read_known_words,
    resolve_base,
    vocabulary,
    words_of,
)


def commit(repo, git, message, files=None):
    for name, content in (files or {}).items():
        path = repo / name
        path.parent.mkdir(parents=True, exist_ok=True)
        if isinstance(content, bytes):
            path.write_bytes(content)
        else:
            path.write_text(content, encoding="utf-8")
        git(repo, "add", name)
    git(repo, "commit", "-q", "--allow-empty", "-m", message)
    return git(repo, "rev-parse", "HEAD").stdout.strip()


def words(found):
    return [item.word for item in found]


def new_in_last_commit(repo, table, **kwargs):
    return check_range(repo, ["HEAD~1..HEAD"], table, kwargs.pop("against", "HEAD~1"), **kwargs)


def test_words_split_on_underscores_digits_and_camel_case_edges():
    text = "ACME_API acme2Corp HTTPServer NamesTable ab Zo iPhone"
    assert list(words_of(text)) == [
        "ACME",
        "API",
        "acme",
        "Corp",
        "HTTP",
        "Server",
        "Names",
        "Table",
        "Phone",
    ]


def test_a_decomposed_accent_stays_inside_its_word():
    assert list(words_of("Méridia")) == ["Méridia"]


def test_an_identifier_gives_each_of_its_words(repo, git, table):
    commit(repo, git, "base", {"a.md": "fine\n"})
    commit(repo, git, "two", {"a.md": "fine\nZORBLAX_API\n"})
    assert words(new_in_last_commit(repo, table)) == ["ZORBLAX", "API"]


def test_a_sentence_start_word_is_known_through_its_lowercase_form(repo, git, table):
    commit(repo, git, "base", {"a.md": "depois de tudo\n"})
    commit(repo, git, "two", {"a.md": "depois de tudo\nDepois chegou o Zorblax\n"})
    assert words(new_in_last_commit(repo, table)) == ["Zorblax"]


def test_known_words_ignore_accents_and_case(repo, git, table):
    commit(repo, git, "base", {"a.md": "o açúcar e a ÉPOCA\n"})
    commit(repo, git, "two", {"a.md": "o açúcar e a ÉPOCA\nAcucar Epoca ACUCAR Açúcar\n"})
    assert new_in_last_commit(repo, table) == []


def test_lowercase_words_and_short_words_are_not_checked(repo, git, table):
    commit(repo, git, "base", {"a.md": "fine\n"})
    commit(repo, git, "two", {"a.md": "fine\nzorblax Zo\n"})
    assert new_in_last_commit(repo, table) == []


def test_an_analog_is_known_even_when_nothing_is_pushed(repo, git, table):
    commit(repo, git, "base", {"a.md": "Apex and Summit Partners and Meridiana\n"})
    assert check_range(repo, ["HEAD"], table, None) == []


def test_a_real_name_of_the_table_is_left_to_check_secrets(repo, git, table):
    commit(repo, git, "base", {"a.md": "theme\n"})
    commit(repo, git, "two", {"a.md": "Acme, ACME and Méridia and Brilliant and AcmeTheme\n"})
    assert new_in_last_commit(repo, table) == []


def test_known_words_file_of_the_tip_is_known(repo, git, table):
    commit(repo, git, "base", {"a.md": "fine\n"})
    commit(repo, git, "two", {"a.md": "fine\nZorblax\n", KNOWN_WORDS_FILE: "# why\nzorblax\n"})
    assert new_in_last_commit(repo, table) == []
    assert words(new_in_last_commit(repo, table, tip="HEAD~1")) == ["Zorblax"]


def test_a_word_in_a_commit_message_is_found_with_its_line(repo, git, table):
    commit(repo, git, "base", {"a.md": "fine\n"})
    commit(repo, git, "feat: integra\n\nparceiro Quuxmark")
    found = new_in_last_commit(repo, table)
    assert found[0].word == "Quuxmark"
    assert found[0].places == (Place("message", 3, git(repo, "rev-parse", "HEAD").stdout.strip()),)


def test_a_word_already_in_the_pushed_state_is_known(repo, git, table):
    pushed = commit(repo, git, "base", {"a.md": "the Quuxmark team\n"})
    commit(repo, git, "two", {"b.md": "Quuxmark again\n"})
    assert check_range(repo, [f"{pushed}..HEAD"], table, pushed) == []
    assert words(check_range(repo, [f"{pushed}..HEAD"], table, None)) == ["Quuxmark"]


def test_the_vocabulary_is_the_pushed_state_not_the_unpushed_commits(repo, git, table):
    pushed = commit(repo, git, "base", {"a.md": "fine\n"})
    commit(repo, git, "one", {"b.md": "Quuxmark\n"})
    commit(repo, git, "two", {"c.md": "Quuxmark\n"})
    found = check_range(repo, [f"{pushed}..HEAD"], table, pushed)
    assert [(place.path, place.line) for place in found[0].places] == [("b.md", 1), ("c.md", 1)]


def test_a_word_added_and_removed_inside_the_range_is_still_found(repo, git, table):
    pushed = commit(repo, git, "base", {"a.md": "fine\n"})
    commit(repo, git, "add", {"a.md": "fine\nQuuxmark\n"})
    commit(repo, git, "remove", {"a.md": "fine\n"})
    assert words(check_range(repo, [f"{pushed}..HEAD"], table, pushed)) == ["Quuxmark"]


def test_lines_that_were_already_there_are_not_added_by_the_commit(repo, git, table):
    commit(repo, git, "base", {"a.md": "Quuxmark\nfine\n"})
    commit(repo, git, "two", {"a.md": "Quuxmark\nfine\nmore\n"})
    assert new_in_last_commit(repo, table, against=None) == []


def test_spellings_of_a_word_are_one_entry_with_every_place(repo, git, table):
    commit(repo, git, "base", {"a.md": "fine\n"})
    commit(repo, git, "two", {"a.md": "fine\nZorblax ZORBLAX\nzorblax Zorblax\n"})
    found = new_in_last_commit(repo, table)
    assert words(found) == ["Zorblax"]
    assert [place.line for place in found[0].places] == [2, 3]


def test_a_merge_adds_no_lines_of_its_own_but_its_message_is_read(repo, git, table):
    base = commit(repo, git, "base", {"a.md": "fine\n"})
    git(repo, "switch", "-q", "-c", "side")
    side = commit(repo, git, "side", {"side.md": "Zorblax\n"})
    git(repo, "switch", "-q", "-")
    commit(repo, git, "main", {"main.md": "fine\n"})
    git(repo, "merge", "--no-ff", "-q", "-m", "chore: junta Quuxmark", "side")
    found = check_range(repo, ["HEAD", "--not", base], table, None)
    assert {item.word: [place.commit for place in item.places] for item in found} == {
        "Zorblax": [side],
        "Quuxmark": [git(repo, "rev-parse", "HEAD").stdout.strip()],
    }


def test_a_binary_file_is_not_read(repo, git, table):
    commit(repo, git, "base", {"a.md": "fine\n"})
    commit(repo, git, "two", {"blob.bin": b"\0Zorblax\0"})
    assert new_in_last_commit(repo, table) == []
    assert "zorblax" not in vocabulary(repo, "HEAD")


def test_staged_check_reads_only_the_added_lines(repo, git, table):
    commit(repo, git, "base", {"a.md": "Quuxmark\nfine\n"})
    (repo / "a.md").write_text("Quuxmark\nfine\nZorblax\n", encoding="utf-8")
    git(repo, "add", "a.md")
    found = check_staged(repo, table, "HEAD")
    assert [(item.word, str(item.places[0])) for item in found] == [("Zorblax", "a.md:3")]


def test_staged_check_reads_known_words_from_the_index(repo, git, table):
    commit(repo, git, "base", {"a.md": "fine\n"})
    (repo / "a.md").write_text("fine\nZorblax\n", encoding="utf-8")
    (repo / KNOWN_WORDS_FILE).write_text("Zorblax\n", encoding="utf-8")
    git(repo, "add", "a.md")
    assert words(check_staged(repo, table, "HEAD")) == ["Zorblax"]
    git(repo, "add", KNOWN_WORDS_FILE)
    assert check_staged(repo, table, "HEAD") == []


def test_a_message_file_skips_the_comment_lines_git_drops(repo, git, table):
    commit(repo, git, "base", {"a.md": "fine\n"})
    text = "fix: x\n\nQuuxmark\n# Zorblax is in a comment\n"
    found = check_message(repo, text, table, "HEAD")
    assert [(item.word, str(item.places[0])) for item in found] == [("Quuxmark", "message:3")]


def test_known_words_file_syntax():
    assert parse_known_words("# why\n\nCelery\n  Açúcar  \n") == {"celery", "acucar"}
    with pytest.raises(ValueError, match=r"line 2: expected one word"):
        parse_known_words("Celery\nCelery Beat\n")
    with pytest.raises(ValueError, match="line 1"):
        parse_known_words("Celery # trailing comment\n")


def test_known_words_are_read_from_a_commit_and_from_the_index(repo, git):
    assert read_known_words(repo) == frozenset()
    commit(repo, git, "base", {KNOWN_WORDS_FILE: "Celery\n"})
    (repo / KNOWN_WORDS_FILE).write_text("Celery\nDatadog\n", encoding="utf-8")
    assert read_known_words(repo, "HEAD") == {"celery"}
    assert read_known_words(repo) == {"celery"}
    git(repo, "add", KNOWN_WORDS_FILE)
    assert read_known_words(repo) == {"celery", "datadog"}
    with pytest.raises(RuntimeError):
        read_known_words(repo, "no-such-rev")


def test_adding_known_words_creates_the_file_with_its_header_and_skips_duplicates(repo):
    added, skipped = add_known_words(repo, ["Celery", "Datadog", "CELERY", "Açúcar"])
    assert (added, skipped) == (["Celery", "Datadog", "Açúcar"], ["CELERY"])
    text = (repo / KNOWN_WORDS_FILE).read_text(encoding="utf-8")
    assert text.startswith("# ")
    assert text.endswith("Celery\nDatadog\nAçúcar\n")
    assert add_known_words(repo, ["acucar", "celery"]) == ([], ["acucar", "celery"])
    assert (repo / KNOWN_WORDS_FILE).read_text(encoding="utf-8") == text


def test_adding_a_known_word_keeps_what_the_file_has(repo):
    (repo / KNOWN_WORDS_FILE).write_text("# mine\nCelery", encoding="utf-8")
    add_known_words(repo, ["Datadog"])
    assert (repo / KNOWN_WORDS_FILE).read_text(encoding="utf-8") == "# mine\nCelery\nDatadog\n"


@pytest.mark.parametrize("bad", ["two words", "", "Celery2", "a-b"])
def test_adding_something_that_is_not_a_word_is_refused(repo, bad):
    with pytest.raises(ValueError):
        add_known_words(repo, [bad])
    assert not (repo / KNOWN_WORDS_FILE).exists()


def test_the_known_words_file_of_this_repo_parses():
    root = Path(newwords.__file__).resolve().parents[2]
    parse_known_words((root / KNOWN_WORDS_FILE).read_text(encoding="utf-8"))
    parse_known_words(newwords.KNOWN_WORDS_HEADER)


def test_base_is_the_upstream_then_origin_main_then_nothing(repo, git):
    base = commit(repo, git, "base", {"a.md": "fine\n"})
    assert resolve_base(repo) is None
    git(repo, "update-ref", "refs/remotes/origin/main", base)
    assert resolve_base(repo) == "origin/main"
    git(repo, "remote", "add", "origin", str(repo))
    git(repo, "update-ref", "refs/remotes/origin/other", base)
    git(repo, "branch", "--set-upstream-to=origin/other")
    assert resolve_base(repo) == "@{upstream}"


def test_a_range_needs_revisions(repo, table):
    with pytest.raises(ValueError):
        check_range(repo, [], table, None)
