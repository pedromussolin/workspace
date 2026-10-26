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
    ("secret-assignment", "API_TOKEN=abcd1234"),
    ("secret-assignment", "client_secret = abcd1234"),
    ("secret-assignment", "DB_PASSWORD: abcd1234"),
    ("secret-assignment", "AZURE_CLIENT_SECRET=abcd1234"),
    ("secret-assignment", "PGPASSWORD=hunter22 psql -h replica -c 'select 1'"),
    ("secret-assignment", "SECRET_KEY=abcd1234"),
    ("secret-assignment", "AWS_SECRET_ACCESS_KEY=abcd1234"),
    ("secret-assignment", "JWT_SECRET_KEY=abcd1234"),
    ("secret-assignment", "export DB_PASSWORD_PROD=abcd1234"),
    ("secret-assignment", "token_limit = abc12345"),
    ("token-prefix", "export X=" + "ghp_" + "a1" * 12),
    ("token-prefix", "ATATT" + "3xFf" * 8),
    ("url-credentials", "clone https://user:pass@host.example/repo.git"),
    ("io-host", "see api.service.io for details"),
    ("private-ip", "server at 10.1.2.3"),
    ("home-path", "cd /home/someone/work"),
    ("home-path", "cd /mnt/c/Users/someone/Desktop"),
    ("home-path", "cd /mnt/d/users/someone"),
    ("home-path", "C:\\Users\\someone\\Documents"),
    ("home-path", "C:/Users/someone/Documents"),
    ("home-path", '"C:\\\\Users\\\\someone"'),
    ("home-path", "\\\\wsl.localhost\\Distro\\home\\someone\\repos"),
    ("home-path", "\\\\wsl$\\Distro\\home\\someone"),
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
        "the tokenizer: spacy",
        "token_count = 12345",
        "token_limit = 4096",
        "max_tokens: 4096",
        "the tokens: a list",
        'docker run -v "$PWD":/proto image',
        "see C:\\Users\\<name>\\Desktop and /mnt/c/Users/<name>",
        "the C:\\Windows\\System32 folder and /mnt/c/Program Files",
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
    [
        "token: <seu-token>",
        "password = <your password>",
        "api_key=",
        'secret: ""',
        "token = abc",
        "SECRET_KEY=<valor>",
        "API_TOKEN=<valor>",
        "DB_PASSWORD: <senha>",
        "PGPASSWORD=<senha> psql -h <replica-host>",
        "AWS_SECRET_ACCESS_KEY=<chave>",
        "JWT_SECRET_KEY=<valor>",
    ],
)
def test_placeholder_passes(table, line):
    assert rules_of(line, table) == []


def test_placeholder_passes_and_real_value_fails(table):
    assert rules_of("SECRET_KEY=<valor>", table) == []
    assert rules_of("SECRET_KEY=abcd1234", table) == ["secret-assignment"]
    assert rules_of("PGPASSWORD=<senha> psql", table) == []
    assert rules_of("PGPASSWORD=hunter22 psql", table) == ["secret-assignment"]


@pytest.mark.parametrize("line", ["acme_theme: x", "AcmeTheme", "ACME_API_URL=x", "acme2"])
def test_name_inside_an_identifier_fails(table, line):
    assert rules_of(line, table) == ["real-name"]


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


GITHUB_TOKEN = "ghp_" + "a1" * 12
ATLASSIAN_TOKEN = "ATATT" + "3xFf" * 8


@pytest.mark.parametrize(
    ("line", "redacted"),
    [
        ("API_TOKEN=abcd1234", "API_TOKEN=***"),
        ("export client_secret = abcd1234", "client_secret = ***"),
        ("senha: hunter22", "senha: ***"),
        ('"token": "abcd1234"', 'token": "***'),
        ("api_key = 'abcd1234'", "api_key = '***"),
        ("see foo.bar_token=abcd1234", "bar_token=***"),
        (f"export X={GITHUB_TOKEN}", "ghp_***"),
        (f"auth {ATLASSIAN_TOKEN}", "ATAT***"),
        ("clone https://user:pass@host.example/repo.git", "://***@"),
        ("PGPASSWORD=hunter22 psql -h x", "PGPASSWORD=***"),
        ("export AWS_SECRET_ACCESS_KEY=abcd1234", "AWS_SECRET_ACCESS_KEY=***"),
    ],
)
def test_secret_findings_never_carry_the_value(table, line, redacted):
    found = scan_text("f.md", line, table, [])
    assert redacted in [f.match for f in found]
    for finding in found:
        assert not any(value in finding.match for value in ("abcd1234", "hunter22", "pass@"))
        assert GITHUB_TOKEN[4:] not in finding.match
        assert ATLASSIAN_TOKEN[4:] not in finding.match


@pytest.mark.parametrize(
    ("line", "value"),
    [
        ("API_TOKEN=abcd1234", "abcd1234"),
        ("senha: hunter22", "hunter22"),
        (f"export X={GITHUB_TOKEN}", GITHUB_TOKEN[4:]),
        (f"auth {ATLASSIAN_TOKEN}", ATLASSIAN_TOKEN[4:]),
        ("clone https://user:pass@host.example/repo.git", "user:pass"),
    ],
)
def test_cli_output_never_prints_the_secret(repo, git, ws_config, monkeypatch, capsys, line, value):
    monkeypatch.chdir(repo)
    stage(repo, git, "notes.md", line + "\n")
    assert main(["check-secrets"]) == 1
    captured = capsys.readouterr()
    assert value not in captured.out + captured.err
    assert "***" in captured.out


def test_other_rules_keep_the_match(table):
    text = "10.1.2.3 and /home/someone and api.service.io"
    assert [f.match for f in scan_text("f.md", text, table, [])] == [
        "api.service.io",
        "10.1.2.3",
        "/home/someone",
    ]


def test_redaction_does_not_change_allowlist_matching(table):
    allow = [AllowRule("f.md", "secret-assignment", re.compile("abcd1234"))]
    assert scan_text("f.md", "API_TOKEN=abcd1234", table, allow) == []
    assert scan_text("f.md", "API_TOKEN=other999", table, allow) != []


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
