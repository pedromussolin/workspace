import re

import pytest

from ws.secrets import AllowRule, check_repo, load_allowlist, parse_allowlist, scan_text

# Written in two pieces so that this file does not match the home-path rule itself.
PORTAL_FILE = "features/general/ho" + "me/home.page.ts"
HOME_FOLDER = "/ho" + "me/someone"
PORTAL_ENTRY = AllowRule("**", "home-path", re.compile(r"general/home/[\w.-]*"))


def found(path, text, table, allow):
    return [(f.line, f.rule, f.match) for f in scan_text(path, text, table, allow)]


def test_an_entry_allows_only_the_text_it_matches(table):
    allow = [AllowRule("**", "real-name", re.compile("Brillian[t]"))]
    text = "Brilliant is the analog of Méridia"
    assert found("a.md", text, table, allow) == [(1, "real-name", "Méridia")]


def test_an_allowed_path_does_not_hide_a_real_home_path_on_the_same_line(table):
    line = f"{HOME_FOLDER}/repos/front/src/app/{PORTAL_FILE}"
    assert found("a.md", f"see {PORTAL_FILE}", table, [PORTAL_ENTRY]) == []
    assert found("a.md", line, table, [PORTAL_ENTRY]) == [(1, "home-path", HOME_FOLDER)]


def test_a_match_next_to_the_finding_does_not_allow_it(table):
    allow = [AllowRule("**", "*", re.compile("example"))]
    assert found("a.md", "Acme example", table, allow) != []
    assert found("a.md", "Acmeexample", table, allow) == []


def test_a_match_that_overlaps_only_part_of_the_finding_allows_it(table):
    allow = [AllowRule("**", "real-name", re.compile("Acme C"))]
    assert found("a.md", "ask Acme Capital", table, allow) == []


def test_several_findings_need_an_entry_each(table):
    allow = [AllowRule("**", "real-name", re.compile("Acm[e]"))]
    line = "Acme and Méridia and Acme"
    assert found("a.md", line, table, allow) == [(1, "real-name", "Méridia")]


@pytest.mark.parametrize(
    ("glob", "path", "allowed"),
    [
        ("tests/*.py", "tests/a.py", True),
        ("tests/*.py", "tests/x/a.py", False),
        ("tests/*.py", "tests/a.pyc", False),
        ("tests/**", "tests/x/y/a.py", True),
        ("tests/**", "other/a.py", False),
        ("tests/**/*.py", "tests/a.py", True),
        ("tests/**/*.py", "tests/x/y/a.py", True),
        ("tests/**/*.py", "tests/x/a.md", False),
        ("**/a.py", "a.py", True),
        ("**/a.py", "x/y/a.py", True),
        ("**/a.py", "x/ba.py", False),
        ("a?.md", "ab.md", True),
        ("a?.md", "a/.md", False),
        ("a.md", "aXmd", False),
        ("a.md", "docs/a.md", False),
        ("a[1].md", "a[1].md", True),
    ],
)
def test_path_globs(table, glob, path, allowed):
    allow = [AllowRule(glob, "real-name", re.compile("Acm[e]"))]
    assert (found(path, "Acme", table, allow) == []) is allowed


def write_allowlist(repo, content):
    (repo / ".secrets-allow").write_text(content, encoding="utf-8")


def stage(repo, git, name, content):
    (repo / name).write_text(content, encoding="utf-8")
    git(repo, "add", name)


def test_an_exception_only_in_the_work_tree_does_not_count(repo, git, table):
    stage(repo, git, "notes.md", "Acme\n")
    write_allowlist(repo, "notes.md real-name Acm[e]\n")
    assert [f.rule for f in check_repo(repo, "staged", table)] == ["real-name"]


def test_a_staged_exception_counts(repo, git, table):
    stage(repo, git, "notes.md", "Acme\n")
    stage(repo, git, ".secrets-allow", "notes.md real-name Acm[e]\n")
    assert check_repo(repo, "staged", table) == []


def test_the_staged_version_of_the_allowlist_wins_over_the_work_tree(repo, git, table):
    stage(repo, git, "notes.md", "Acme\n")
    stage(repo, git, ".secrets-allow", "notes.md real-name Méridi[a]\n")
    write_allowlist(repo, "notes.md real-name Acm[e]\n")
    assert [f.rule for f in check_repo(repo, "staged", table)] == ["real-name"]


def test_a_committed_exception_that_left_the_index_does_not_count(repo, git, table):
    stage(repo, git, ".secrets-allow", "notes.md real-name Acm[e]\n")
    git(repo, "commit", "-q", "-m", "base")
    git(repo, "rm", "-q", "--cached", ".secrets-allow")
    stage(repo, git, "notes.md", "Acme\n")
    assert [f.rule for f in check_repo(repo, "staged", table)] == ["real-name"]


def test_an_unstaged_wildcard_entry_lets_nothing_through(repo, git, table):
    stage(repo, git, "notes.md", "Acme\n")
    write_allowlist(repo, "docs/** * .*\n")
    assert [f.rule for f in check_repo(repo, "staged", table)] == ["real-name"]


def test_paths_mode_reads_the_allowlist_of_the_work_tree(repo, table):
    (repo / "notes.md").write_text("Acme\n", encoding="utf-8")
    write_allowlist(repo, "notes.md real-name Acm[e]\n")
    assert check_repo(repo, "paths", table, [repo / "notes.md"]) == []


@pytest.mark.parametrize("entry", ["* * .*", "** * .*", "**/* * x", "*/** * x", "*** * x"])
def test_a_wildcard_rule_with_a_glob_for_every_file_is_rejected(entry):
    with pytest.raises(ValueError, match=r"\.secrets-allow line 1: a rule \* entry"):
        parse_allowlist(entry + "\n")


@pytest.mark.parametrize("entry", ["docs/** * x", "*.md * x", "** real-name x", "a/*/b * x"])
def test_narrow_wildcard_rule_entries_and_wide_globs_with_a_rule_are_accepted(entry):
    assert len(parse_allowlist(entry + "\n")) == 1


def test_the_repo_allowlist_parses_and_has_no_blanket_entry():
    from ws.config import repo_root

    rules = load_allowlist(repo_root())
    assert rules
    assert not [rule for rule in rules if rule.rule == "*" and rule.path_glob.strip("*/") == ""]
