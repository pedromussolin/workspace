"""Staged content that git's default diff view would hide from the check."""

import pytest

from ws.secrets import check_repo, parse_allowlist, staged_additions


def stage(repo, git, name, content):
    path = repo / name
    path.parent.mkdir(parents=True, exist_ok=True)
    if isinstance(content, bytes):
        path.write_bytes(content)
    else:
        path.write_text(content, encoding="utf-8")
    git(repo, "add", name)


def summary(findings):
    return [(f.path, f.line, f.rule) for f in findings]


def test_a_file_marked_no_diff_is_still_read(repo, git, table):
    stage(repo, git, ".gitattributes", "*.md -diff\n*.svg binary\n")
    git(repo, "commit", "-q", "-m", "attributes")
    stage(repo, git, "notes.md", "fine\nAcme\n")
    stage(repo, git, "logo.svg", "<svg>Acme</svg>\n")
    assert summary(check_repo(repo, "staged", table)) == [
        ("logo.svg", 1, "real-name"),
        ("notes.md", 2, "real-name"),
    ]


def test_a_text_converter_does_not_hide_the_content(repo, git, table):
    stage(repo, git, ".gitattributes", "*.md diff=strip\n")
    git(repo, "config", "diff.strip.textconv", "echo converted")
    git(repo, "commit", "-q", "-m", "attributes")
    stage(repo, git, "notes.md", "Acme\n")
    assert summary(check_repo(repo, "staged", table)) == [("notes.md", 1, "real-name")]


def test_a_symlink_replaced_by_a_regular_file_is_checked(repo, git, table):
    (repo / "link").symlink_to("target.md")
    git(repo, "add", "link")
    git(repo, "commit", "-q", "-m", "base")
    (repo / "link").unlink()
    stage(repo, git, "link", "Acme\n")
    assert summary(check_repo(repo, "staged", table)) == [("link", 1, "real-name")]


def test_a_new_symlink_is_checked_as_its_target_text(repo, git, table):
    (repo / "link").symlink_to("notes/Acme.md")
    git(repo, "add", "link")
    assert summary(check_repo(repo, "staged", table)) == [("link", 1, "real-name")]


def test_a_pure_rename_is_checked_again_at_the_new_path(repo, git, table):
    stage(repo, git, ".secrets-allow", "old.md real-name Acm[e]\n")
    stage(repo, git, "old.md", "Acme\n")
    git(repo, "commit", "-q", "-m", "base")
    git(repo, "mv", "old.md", "new.md")
    assert summary(check_repo(repo, "staged", table)) == [("new.md", 1, "real-name")]


def test_a_copy_is_checked_too(repo, git, table):
    stage(repo, git, "old.md", "Acme\n" * 8)
    git(repo, "commit", "-q", "-m", "base")
    stage(repo, git, "copy.md", "Acme\n" * 8)
    assert [f.path for f in check_repo(repo, "staged", table)] == ["copy.md"] * 8


def test_a_staged_binary_is_a_finding(repo, git, table):
    stage(repo, git, "shot.png", b"\x89PNG\r\n\x1a\n\x00\x00Acme")
    found = check_repo(repo, "staged", table)
    assert summary(found) == [("shot.png", 1, "binary-file")]
    assert found[0].match == "binary file"


def test_a_binary_needs_an_entry_whose_glob_names_it(repo, git, table):
    stage(repo, git, "img/shot.png", b"\x89PNG\x00")
    stage(repo, git, "other/shot.png", b"\x89PNG\x00")
    stage(repo, git, ".secrets-allow", "img/*.png binary-file .*\n")
    assert summary(check_repo(repo, "staged", table)) == [("other/shot.png", 1, "binary-file")]


def test_a_binary_entry_with_a_regex_that_misses_the_path_does_not_allow_it(repo, git, table):
    stage(repo, git, "img/shot.png", b"\x89PNG\x00")
    stage(repo, git, ".secrets-allow", "img/*.png binary-file other\n")
    assert summary(check_repo(repo, "staged", table)) == [("img/shot.png", 1, "binary-file")]


def test_a_rule_star_entry_can_allow_a_binary_by_its_path(repo, git, table):
    stage(repo, git, "img/shot.png", b"\x89PNG\x00")
    stage(repo, git, ".secrets-allow", "img/** * shot\n")
    assert check_repo(repo, "staged", table) == []


def test_binary_file_is_a_known_rule():
    assert parse_allowlist("img/*.png binary-file .*\n")[0].rule == "binary-file"


@pytest.mark.parametrize("encoding", ["utf-16", "utf-16-le", "utf-16-be", "utf-32"])
def test_text_with_a_bom_is_decoded_and_checked(repo, git, table, encoding):
    content = "﻿fine\r\nsee Acme here\r\n".encode(encoding)
    stage(repo, git, "export.txt", content)
    assert summary(check_repo(repo, "staged", table)) == [("export.txt", 2, "real-name")]


def test_utf_16_without_a_bom_counts_as_binary(repo, git, table):
    stage(repo, git, "export.txt", "Acme\n".encode("utf-16-le"))
    assert summary(check_repo(repo, "staged", table)) == [("export.txt", 1, "binary-file")]


def test_a_changed_utf_16_file_is_scanned_whole(repo, git, table):
    stage(repo, git, "export.txt", "Acme\none\n".encode("utf-16"))
    git(repo, "commit", "-q", "-m", "base")
    stage(repo, git, "export.txt", "Acme\ntwo\n".encode("utf-16"))
    assert summary(check_repo(repo, "staged", table)) == [("export.txt", 1, "real-name")]


def test_a_submodule_entry_is_skipped(repo, git, table):
    git(
        repo,
        "update-index",
        "--add",
        "--cacheinfo",
        "160000,1111111111111111111111111111111111111111,vendor/lib",
    )
    stage(repo, git, "notes.md", "fine\n")
    assert check_repo(repo, "staged", table) == []
    assert check_repo(repo, "all", table) == []


def test_staged_additions_ignore_a_submodule_but_not_the_file_next_to_it(repo, git):
    git(
        repo,
        "update-index",
        "--add",
        "--cacheinfo",
        "160000,1111111111111111111111111111111111111111,vendor/lib",
    )
    stage(repo, git, "notes.md", "one\n")
    assert staged_additions(repo) == {"notes.md": {1}}


def test_a_name_with_odd_characters_is_checked(repo, git, table):
    stage(repo, git, "my notes/né.md", "Acme\n")
    assert summary(check_repo(repo, "staged", table)) == [("my notes/né.md", 1, "real-name")]
