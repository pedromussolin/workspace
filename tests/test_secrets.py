import re

import pytest

from ws import secrets
from ws.cli import main
from ws.names import NamesTable
from ws.secrets import (
    AllowRule,
    Finding,
    check_repo,
    load_allowlist,
    scan_text,
    staged_additions,
)

SAMPLES = [
    ("secret-assignment", "password = hunter22"),
    ("secret-assignment", 'api_key: "abcd1234"'),
    ("secret-assignment", "SENHA=abc123"),
    ("secret-assignment", '"token": "abcd1234"'),
    ("token-prefix", "export X=" + "ghp_" + "a1" * 12),
    ("token-prefix", "ATATT" + "3xFf" * 8),
    ("url-credentials", "clone https://user:pass@host.example/repo.git"),
    ("io-host", "see api.service.io for details"),
    ("private-ip", "server at 10.1.2.3"),
    ("home-path", "cd /home/someone/work"),
    ("real-name", "ping Méridia about it"),
    ("blocked-domain", "open https://www.ACME-CORP.example/page"),
]


def rules_of(text: str, table: NamesTable, allow: list[AllowRule] | None = None) -> list[str]:
    return [finding.rule for finding in scan_text("f.md", text, table, allow or [])]


@pytest.mark.parametrize(("rule", "line"), SAMPLES)
def test_each_rule_fires(table, rule, line):
    assert rule in rules_of(line, table)


@pytest.mark.parametrize(
    "line",
    [
        "sem senha no texto",
        "o token de design primário",
        "never commit a password to git",
        "the secret of good prose is rewriting",
        "a brilliant idea",
        "Acmeville is a town",
        "see 110.1.2.3 and 10.1.2",
        "https://example.org/path@v2",
        "the home folder holds /homepage",
    ],
)
def test_prose_passes(table, line):
    assert rules_of(line, table) == []


@pytest.mark.parametrize(
    "line",
    ["token: <seu-token>", "password = <your password>", "api_key=", 'secret: ""', "token = abc"],
)
def test_placeholder_passes(table, line):
    assert rules_of(line, table) == []


def test_capitalized_partner_word_fails_but_prose_passes(table):
    assert rules_of("Brilliant results", table) == ["real-name"]
    assert rules_of("brilliant results", table) == []


def test_finding_carries_position_and_match(table):
    text = "fine\nsee 10.1.2.3 and Acme\nfine\n"
    assert scan_text("a/b.md", text, table, []) == [
        Finding("a/b.md", 2, "private-ip", "10.1.2.3"),
        Finding("a/b.md", 2, "real-name", "Acme"),
    ]


def test_name_wrapped_across_lines_is_found_on_its_first_line(table):
    text = "one\nwith Acme\nCapital here\n"
    assert [(f.line, f.rule) for f in scan_text("a.md", text, table, [])] == [(2, "real-name")]


def test_only_lines_restricts_the_scan(table):
    text = "Acme\n10.1.2.3\nMéridia\n"
    found = scan_text("a.md", text, table, [], only_lines={2, 3})
    assert [(f.line, f.rule) for f in found] == [(2, "private-ip"), (3, "real-name")]


def test_lines_are_split_only_on_newlines(table):
    text = "one\x0ctwo three\nMéridia\n"
    assert [f.line for f in scan_text("a.md", text, table, [])] == [2]


def write_allowlist(repo, content):
    (repo / ".secrets-allow").write_text(content, encoding="utf-8")


def test_allowlist_parsing(repo):
    write_allowlist(
        repo,
        "# comment\n\ndocs/*.md real-name Brilliant\ntests/x.py * .* with spaces\n",
    )
    assert load_allowlist(repo) == [
        AllowRule("docs/*.md", "real-name", re.compile("Brilliant")),
        AllowRule("tests/x.py", "*", re.compile(".* with spaces")),
    ]


def test_allowlist_missing_file_is_empty(repo):
    assert load_allowlist(repo) == []


@pytest.mark.parametrize(
    "content",
    ["docs/*.md real-name\n", "docs/*.md no-such-rule x\n", "docs/*.md real-name (\n"],
)
def test_malformed_allowlist_is_an_error(repo, content):
    write_allowlist(repo, content)
    with pytest.raises(ValueError, match=r"\.secrets-allow line 1"):
        load_allowlist(repo)


def test_allowlist(repo, git, table):
    (repo / "docs").mkdir()
    (repo / "docs" / "a.md").write_text("Brilliant\nAcme\n10.1.2.3\n", encoding="utf-8")
    (repo / "other").mkdir()
    (repo / "other" / "b.md").write_text("Brilliant\n", encoding="utf-8")
    write_allowlist(repo, "docs/*.md real-name Brilliant\n")
    git(repo, "add", "docs", "other")
    found = check_repo(repo, "staged", table)
    assert [(f.path, f.line, f.rule) for f in found] == [
        ("docs/a.md", 2, "real-name"),
        ("docs/a.md", 3, "private-ip"),
        ("other/b.md", 1, "real-name"),
    ]


def test_allow_any_rule(table):
    allow = [AllowRule("a.md", "*", re.compile("example"))]
    assert scan_text("a.md", "10.1.2.3 example", table, allow) == []
    assert scan_text("b.md", "10.1.2.3 example", table, allow) != []


def stage(repo, git, name, content):
    (repo / name).write_text(content, encoding="utf-8")
    git(repo, "add", name)


def test_partial_staging(repo, git, table):
    stage(repo, git, "notes.md", "one\n")
    git(repo, "commit", "-q", "-m", "base")
    staged = "one\nMéridia\ntwo\n"
    stage(repo, git, "notes.md", staged)
    (repo / "notes.md").write_text("Acme\n" + staged, encoding="utf-8")
    found = check_repo(repo, "staged", table)
    assert [(f.path, f.line, f.match) for f in found] == [("notes.md", 2, "Méridia")]


def test_same_name_in_a_staged_hunk_fails(repo, git, table):
    stage(repo, git, "notes.md", "one\nAcme\n")
    assert [f.match for f in check_repo(repo, "staged", table)] == ["Acme"]


def test_staged_checks_only_added_lines(repo, git, table):
    stage(repo, git, "notes.md", "Acme\nold\n")
    git(repo, "commit", "-q", "-m", "base")
    stage(repo, git, "notes.md", "Acme\nnew\n")
    assert check_repo(repo, "staged", table) == []


def test_staged_additions_line_numbers(repo, git):
    stage(repo, git, "notes.md", "a\nb\nc\nd\ne\n")
    git(repo, "commit", "-q", "-m", "base")
    stage(repo, git, "notes.md", "a\nX\nc\nd\nY\nZ\n")
    stage(repo, git, "new file.md", "n1\nn2\n")
    assert staged_additions(repo) == {"notes.md": {2, 5, 6}, "new file.md": {1, 2}}


def test_staged_additions_ignores_deleted_files_and_pure_deletions(repo, git):
    stage(repo, git, "gone.md", "x\n")
    stage(repo, git, "kept.md", "a\nb\n")
    git(repo, "commit", "-q", "-m", "base")
    git(repo, "rm", "-q", "gone.md")
    stage(repo, git, "kept.md", "a\n")
    assert staged_additions(repo) == {}


def test_added_line_that_looks_like_a_diff_header(repo, git, table):
    stage(repo, git, "patch.md", "ok\n++ b/other.md\nAcme\n")
    assert [(f.path, f.line) for f in check_repo(repo, "staged", table)] == [("patch.md", 3)]


def test_staged_reads_the_index_not_the_work_tree(repo, git, table):
    stage(repo, git, "notes.md", "clean\n")
    (repo / "notes.md").write_text("Acme\n", encoding="utf-8")
    assert check_repo(repo, "staged", table) == []


def test_staged_with_nothing_staged(repo, table):
    assert check_repo(repo, "staged", table) == []


def test_all_mode_skips_binary(repo, git, table):
    (repo / "image.bin").write_bytes(b"\x00\x01Acme\x00")
    stage(repo, git, "notes.md", "Acme\n")
    git(repo, "add", "image.bin")
    found = check_repo(repo, "all", table)
    assert [f.path for f in found] == ["notes.md"]


def test_all_mode_reads_the_work_tree_and_skips_deleted_files(repo, git, table):
    stage(repo, git, "gone.md", "x\n")
    stage(repo, git, "notes.md", "clean\n")
    (repo / "notes.md").write_text("Acme\n", encoding="utf-8")
    (repo / "gone.md").unlink()
    assert [f.path for f in check_repo(repo, "all", table)] == ["notes.md"]


def test_paths_mode(repo, table, tmp_path):
    inside = repo / "a.md"
    inside.write_text("Acme\n", encoding="utf-8")
    outside = tmp_path / "outside.md"
    outside.write_text("10.1.2.3\n", encoding="utf-8")
    found = check_repo(repo, "paths", table, [inside, outside])
    assert [(f.path, f.rule) for f in found] == [
        ("a.md", "real-name"),
        (str(outside), "private-ip"),
    ]


def test_unknown_mode_is_an_error(repo, table):
    with pytest.raises(ValueError, match="mode"):
        check_repo(repo, "nope", table)


def test_cli_exit_codes(repo, git, ws_config, monkeypatch, capsys):
    monkeypatch.chdir(repo)
    stage(repo, git, "notes.md", "fine\n")
    assert main(["check-secrets"]) == 0
    assert capsys.readouterr().out == ""

    stage(repo, git, "notes.md", "fine\nAcme\n")
    assert main(["check-secrets", "--staged"]) == 1
    assert capsys.readouterr().out == (
        "notes.md:2: real-name: Acme\n"
        "1 finding(s): fix them or add a reviewed line to .secrets-allow\n"
    )

    monkeypatch.setenv("WS_CONFIG_DIR", str(repo / "empty"))
    assert main(["check-secrets"]) == 2
    expected = f"names table not found at {repo / 'empty' / 'names.toml'}; the check fails closed"
    assert capsys.readouterr().err.strip() == expected


def test_cli_all_and_paths(repo, git, ws_config, monkeypatch, capsys):
    monkeypatch.chdir(repo)
    stage(repo, git, "notes.md", "Brilliant\n")
    assert main(["check-secrets", "--all"]) == 1
    assert "notes.md:1: real-name: Brilliant" in capsys.readouterr().out
    assert main(["check-secrets", "notes.md"]) == 1
    assert "notes.md:1: real-name: Brilliant" in capsys.readouterr().out


def test_cli_prints_a_wrapped_match_on_one_line(repo, git, ws_config, monkeypatch, capsys):
    monkeypatch.chdir(repo)
    stage(repo, git, "notes.md", "with Acme\nCapital\n")
    assert main(["check-secrets"]) == 1
    assert "notes.md:1: real-name: Acme Capital\n" in capsys.readouterr().out


def test_cli_rejects_paths_together_with_a_mode(repo, ws_config, monkeypatch, capsys):
    monkeypatch.chdir(repo)
    assert main(["check-secrets", "--all", "notes.md"]) == 2
    assert "either" in capsys.readouterr().err


def test_internal_error_blocks(repo, git, ws_config, monkeypatch, capsys):
    monkeypatch.chdir(repo)
    stage(repo, git, "notes.md", "fine\n")

    def explode(*args, **kwargs):
        raise RuntimeError("boom")

    monkeypatch.setattr(secrets, "scan_text", explode)
    assert main(["check-secrets"]) == 1
    assert capsys.readouterr().err.strip() == "check-secrets failed (boom); blocking"


def test_outside_a_repo_blocks(tmp_path, ws_config, git, monkeypatch, capsys):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("GIT_CEILING_DIRECTORIES", str(tmp_path.parent))
    assert main(["check-secrets"]) == 1
    err = capsys.readouterr().err
    assert err.startswith("check-secrets failed (") and err.strip().endswith("; blocking")


def test_malformed_allowlist_blocks(repo, git, ws_config, monkeypatch, capsys):
    monkeypatch.chdir(repo)
    write_allowlist(repo, "only-one-field\n")
    stage(repo, git, "notes.md", "fine\n")
    assert main(["check-secrets"]) == 1
    assert "check-secrets failed (.secrets-allow line 1" in capsys.readouterr().err
