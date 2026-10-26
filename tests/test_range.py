"""`check-secrets --range` and `--message`: what a commit publishes besides its staged diff."""

import pytest

from ws import secrets
from ws.cli import main
from ws.secrets import check_message, check_range

SCISSORS = (
    "# ------------------------ >8 ------------------------\n"
    "# Do not modify or remove the line above.\n"
    "# Everything below it will be ignored.\n"
)


def commit(repo, git, message, files=None, **env):
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


def summary(findings):
    return [(f.path, f.line, f.rule) for f in findings]


def test_added_lines_of_each_commit_are_checked_against_its_first_parent(repo, git, table):
    base = commit(repo, git, "base", {"a.md": "fine\n"})
    first = commit(repo, git, "one", {"a.md": "fine\nAcme\n"})
    commit(repo, git, "two", {"b.md": "also fine\n"})
    found = check_range(repo, [f"{base}..HEAD"], table)
    assert summary(found) == [("a.md", 2, "real-name")]
    assert found[0].commit == first


def test_lines_that_were_already_there_are_not_added_by_the_commit(repo, git, table):
    commit(repo, git, "base", {"a.md": "Acme\nfine\n"})
    second = commit(repo, git, "two", {"a.md": "Acme\nfine\nmore\n"})
    assert check_range(repo, [f"{second}~1..{second}"], table) == []


def test_a_line_added_and_removed_inside_the_range_is_still_found(repo, git, table):
    base = commit(repo, git, "base", {"a.md": "fine\n"})
    commit(repo, git, "add", {"a.md": "fine\nAcme\n"})
    commit(repo, git, "remove", {"a.md": "fine\n"})
    assert summary(check_range(repo, [f"{base}..HEAD"], table)) == [("a.md", 2, "real-name")]


def test_the_root_commit_is_checked(repo, git, table):
    commit(repo, git, "base", {"a.md": "Acme\n"})
    assert summary(check_range(repo, ["HEAD"], table)) == [("a.md", 1, "real-name")]


def test_an_empty_range_has_no_findings(repo, git, table):
    commit(repo, git, "base", {"a.md": "Acme\n"})
    assert check_range(repo, ["HEAD..HEAD"], table) == []


def test_several_words_make_a_rev_list_expression(repo, git, table):
    base = commit(repo, git, "base", {"a.md": "Acme\n"})
    git(repo, "branch", "old")
    commit(repo, git, "new", {"b.md": "fine\n"})
    assert check_range(repo, ["HEAD", "--not", base], table) == []
    assert check_range(repo, ["HEAD", "--not", "old"], table) == []
    assert summary(check_range(repo, ["HEAD"], table)) == [("a.md", 1, "real-name")]


def test_a_commit_message_is_checked_and_is_not_stripped_of_hash_lines(repo, git, table):
    commit(repo, git, "base")
    commit(repo, git, "fix: integração com Acme\n\n# Méridia is the partner")
    found = check_range(repo, ["HEAD~1..HEAD"], table)
    assert summary(found) == [("message", 1, "real-name"), ("message", 3, "real-name")]


def test_a_co_author_trailer_in_a_message_is_a_finding(repo, git, table):
    base = commit(repo, git, "base")
    commit(repo, git, "feat: x\n\nco-authored-by: Someone <someone@example.com>")
    found = check_range(repo, [f"{base}..HEAD"], table)
    assert summary(found) == [("message", 3, "co-authored-by")]


def test_a_co_author_trailer_cannot_be_allowed(repo, git, table):
    commit(repo, git, "base", {".secrets-allow": "message * .*\n"})
    base = commit(repo, git, "base two")
    commit(repo, git, "feat: x\n\nCo-Authored-By: Someone <someone@example.com>")
    assert summary(check_range(repo, [f"{base}..HEAD"], table)) == [
        ("message", 3, "co-authored-by")
    ]


def test_the_words_alone_in_prose_are_not_a_trailer(repo, git, table):
    base = commit(repo, git, "base")
    commit(repo, git, "docs: regra sobre co-authored-by em prosa")
    assert check_range(repo, [f"{base}..HEAD"], table) == []


def test_author_and_committer_e_mails_are_checked_against_the_blocked_domains(
    repo, git, table, monkeypatch
):
    base = commit(repo, git, "base")
    monkeypatch.setenv("GIT_AUTHOR_EMAIL", "pat@ACME-CORP.example")
    monkeypatch.setenv("GIT_COMMITTER_EMAIL", "pat@acme-corp.example")
    commit(repo, git, "feat: x")
    found = check_range(repo, [f"{base}..HEAD"], table)
    assert summary(found) == [("author", 1, "blocked-domain"), ("committer", 1, "blocked-domain")]
    assert found[0].match == "ACME-CORP.example"


def test_a_merge_checks_its_message_and_its_e_mails_but_not_a_diff_of_its_own(repo, git, table):
    commit(repo, git, "base", {"a.md": "fine\n"})
    git(repo, "switch", "-q", "-c", "side")
    commit(repo, git, "side work", {"side.md": "fine\n"})
    git(repo, "switch", "-q", "-")
    commit(repo, git, "main work", {"main.md": "fine\n"})
    git(repo, "merge", "-q", "--no-ff", "-m", "Merge the Acme branch", "side")
    found = check_range(repo, ["HEAD~1..HEAD"], table)
    assert summary(found) == [("message", 1, "real-name")]


def test_an_allowlist_is_read_from_the_commit_that_added_the_lines(repo, git, table):
    base = commit(repo, git, "base", {".secrets-allow": "notes.md real-name Acm[e]\n"})
    commit(repo, git, "allowed", {"notes.md": "Acme\n"})
    commit(repo, git, "drops the entry", {".secrets-allow": "# none\n"})
    later = commit(repo, git, "not allowed any more", {"other.md": "Acme\n"})
    found = check_range(repo, [f"{base}..HEAD"], table)
    assert [(f.commit, f.path) for f in found] == [(later, "other.md")]


def test_a_binary_added_in_a_commit_is_a_finding(repo, git, table):
    base = commit(repo, git, "base")
    commit(repo, git, "image", {"shot.png": b"\x89PNG\x00"})
    assert summary(check_range(repo, [f"{base}..HEAD"], table)) == [("shot.png", 1, "binary-file")]


def test_a_symlink_and_a_name_with_spaces_are_read_at_the_commit(repo, git, table):
    base = commit(repo, git, "base")
    (repo / "link").symlink_to("Acme.md")
    git(repo, "add", "link")
    commit(repo, git, "link", {"my notes/n.md": "Acme\n"})
    found = check_range(repo, [f"{base}..HEAD"], table)
    assert summary(found) == [("link", 1, "real-name"), ("my notes/n.md", 1, "real-name")]


def test_findings_come_oldest_commit_first(repo, git, table):
    base = commit(repo, git, "base")
    first = commit(repo, git, "one", {"a.md": "Acme\n"})
    second = commit(repo, git, "two", {"b.md": "Méridia\n"})
    assert [f.commit for f in check_range(repo, [f"{base}..HEAD"], table)] == [first, second]


def test_a_bad_range_is_an_error(repo, git, table):
    commit(repo, git, "base")
    with pytest.raises(RuntimeError, match="git log failed"):
        check_range(repo, ["nope..HEAD"], table)
    with pytest.raises(ValueError, match="revision range"):
        check_range(repo, [], table)


def test_a_malformed_allowlist_in_a_commit_is_an_error(repo, git, table):
    base = commit(repo, git, "base")
    commit(repo, git, "bad", {".secrets-allow": "only-one-field\n"})
    with pytest.raises(ValueError, match=r"\.secrets-allow line 1"):
        check_range(repo, [f"{base}..HEAD"], table)


def test_a_message_file_with_a_name_is_a_finding(repo, table):
    found = check_message(repo, "fix: integração com Acme\n", table)
    assert summary(found) == [("message", 1, "real-name")]


def test_message_comment_lines_are_skipped(repo, table):
    text = "fix: x\n\n# Please enter the message. Acme is in this line.\n#\tmodified: Acme.md\n"
    assert check_message(repo, text, table) == []


def test_message_lines_are_numbered_with_the_comments_in_place(repo, table):
    text = "fix: x\n# comment\nMéridia\n"
    assert summary(check_message(repo, text, table)) == [("message", 3, "real-name")]


def test_the_diff_under_the_scissors_line_is_not_part_of_the_message(repo, table):
    text = f"fix: x\n\n{SCISSORS}diff --git a/n.md b/n.md\n-Acme\n+Apex\n"
    assert check_message(repo, text, table) == []


def test_text_after_a_lone_scissors_line_is_still_checked(repo, table):
    text = "fix: x\n# ------------------------ >8 ------------------------\nAcme\n"
    assert summary(check_message(repo, text, table)) == [("message", 3, "real-name")]


def test_message_secret_patterns_and_domains_are_found(repo, table):
    text = "fix: x\n\nPGPASSWORD=hunter22 and mail pat@acme-corp.example\n"
    assert {f.rule for f in check_message(repo, text, table)} == {
        "secret-assignment",
        "blocked-domain",
        "real-name",
    }


@pytest.mark.parametrize(
    "line", ["Co-Authored-By: A <a@x.org>", "co-authored-by: A", "  CO-AUTHORED-BY : A"]
)
def test_message_with_a_co_author_trailer_is_rejected(repo, table, line):
    found = check_message(repo, f"feat: x\n\nbody\n\n{line}\n", table)
    assert summary(found) == [("message", 5, "co-authored-by")]


def test_a_message_that_mentions_the_trailer_mid_sentence_passes(repo, table):
    assert check_message(repo, "docs: sem co-authored-by nos commits\n", table) == []


def test_message_uses_the_staged_allowlist(repo, git, table):
    (repo / ".secrets-allow").write_text("message * Acm[e]\n", encoding="utf-8")
    assert summary(check_message(repo, "fix: Acme\n", table)) == [("message", 1, "real-name")]
    git(repo, "add", ".secrets-allow")
    assert check_message(repo, "fix: Acme\n", table) == []


def test_cli_range_prints_the_commit_with_each_finding(repo, git, ws_config, monkeypatch, capsys):
    monkeypatch.chdir(repo)
    base = commit(repo, git, "base")
    first = commit(repo, git, "feat: Acme", {"a.md": "fine\nAcme\n"})
    assert main(["check-secrets", "--range", f"{base}..HEAD"]) == 1
    assert capsys.readouterr().out == (
        f"{first[:10]}:a.md:2: real-name: Acme\n"
        f"{first[:10]}:message:1: real-name: Acme\n"
        "2 finding(s): fix them or add a reviewed line to .secrets-allow\n"
    )


def test_cli_range_clean_and_errors(repo, git, ws_config, monkeypatch, capsys):
    monkeypatch.chdir(repo)
    commit(repo, git, "base", {"a.md": "fine\n"})
    assert main(["check-secrets", "--range", "HEAD"]) == 0
    assert capsys.readouterr().out == ""
    assert main(["check-secrets", "--range", "nope"]) == 1
    assert "check-secrets failed (git log failed" in capsys.readouterr().err
    assert main(["check-secrets", "--range", ""]) == 1
    assert "revision range" in capsys.readouterr().err


def test_cli_message(repo, ws_config, monkeypatch, capsys):
    monkeypatch.chdir(repo)
    message = repo / "MSG"
    message.write_text("fix: x\n\n# Acme\nMéridia\n", encoding="utf-8")
    assert main(["check-secrets", "--message", str(message)]) == 1
    assert capsys.readouterr().out == (
        "message:4: real-name: Méridia\n"
        "1 finding(s): fix them or add a reviewed line to .secrets-allow\n"
    )
    message.write_text("fix: x\n", encoding="utf-8")
    assert main(["check-secrets", "--message", str(message)]) == 0


def test_cli_message_that_cannot_be_read_blocks(repo, ws_config, monkeypatch, capsys):
    monkeypatch.chdir(repo)
    assert main(["check-secrets", "--message", str(repo / "absent")]) == 1
    assert "check-secrets failed" in capsys.readouterr().err


def test_cli_modes_exclude_each_other(repo, ws_config, monkeypatch, capsys):
    monkeypatch.chdir(repo)
    with pytest.raises(SystemExit):
        main(["check-secrets", "--staged", "--range", "HEAD"])
    with pytest.raises(SystemExit):
        main(["check-secrets", "--message", "MSG", "--all"])
    capsys.readouterr()
    assert main(["check-secrets", "--range", "HEAD", "notes.md"]) == 2
    assert main(["check-secrets", "--message", "MSG", "notes.md"]) == 2
    assert "either" in capsys.readouterr().err


def test_a_missing_names_table_blocks_range_and_message(repo, tmp_path, monkeypatch, capsys):
    monkeypatch.chdir(repo)
    monkeypatch.setenv("WS_CONFIG_DIR", str(tmp_path / "no-config"))
    assert main(["check-secrets", "--range", "HEAD"]) == 2
    assert main(["check-secrets", "--message", "MSG"]) == 2
    assert capsys.readouterr().err.count("the check fails closed") == 2


def test_an_internal_error_in_range_blocks(repo, git, ws_config, monkeypatch, capsys):
    monkeypatch.chdir(repo)
    commit(repo, git, "base", {"a.md": "fine\n"})

    def explode(*args, **kwargs):
        raise RuntimeError("boom")

    monkeypatch.setattr(secrets, "scan_text", explode)
    assert main(["check-secrets", "--range", "HEAD"]) == 1
    assert capsys.readouterr().err.strip() == "check-secrets failed (boom); blocking"
