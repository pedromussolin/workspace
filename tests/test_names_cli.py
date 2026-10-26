"""`ws names`: check, pending, known, add and review."""

import io
import json
import stat

import pytest

from ws.cli import main
from ws.names import load_names

MESSAGE = "feat: integra o Zorblax"


def commit(repo, git, message, files=None):
    for name, content in (files or {}).items():
        (repo / name).write_text(content, encoding="utf-8")
        git(repo, "add", name)
    git(repo, "commit", "-q", "--allow-empty", "-m", message)
    return git(repo, "rev-parse", "HEAD").stdout.strip()


@pytest.fixture
def unpushed(repo, git, monkeypatch):
    """A repo whose origin/main knows `fine`, with one local commit that adds three new words."""
    base = commit(repo, git, "base", {"base.md": "fine\n"})
    git(repo, "update-ref", "refs/remotes/origin/main", base)
    sha = commit(repo, git, MESSAGE, {"notes.md": "Zorblax and Quuxmark and Frobnitz\n"})
    monkeypatch.chdir(repo)
    return sha


def stdin(monkeypatch, text):
    monkeypatch.setattr("sys.stdin", io.StringIO(text))


def test_pending_lists_each_word_with_where_it_appears(unpushed, ws_config, capsys):
    assert main(["names", "pending"]) == 0
    short = unpushed[:10]
    assert capsys.readouterr().out.splitlines() == [
        f"Zorblax: {short}:message:1, {short}:notes.md:1",
        f"Quuxmark: {short}:notes.md:1",
        f"Frobnitz: {short}:notes.md:1",
    ]


def test_pending_as_json(unpushed, ws_config, capsys):
    assert main(["names", "pending", "--json"]) == 0
    listing = json.loads(capsys.readouterr().out)
    assert [item["word"] for item in listing] == ["Zorblax", "Quuxmark", "Frobnitz"]
    assert listing[0]["places"] == [
        {"commit": unpushed, "path": "message", "line": 1},
        {"commit": unpushed, "path": "notes.md", "line": 1},
    ]


def test_pending_is_empty_when_everything_is_known(unpushed, repo, git, ws_config, capsys):
    commit(repo, git, "chore: x", {".known-words": "Zorblax\nQuuxmark\nFrobnitz\n"})
    assert main(["names", "pending", "--json"]) == 0
    assert json.loads(capsys.readouterr().out) == []


def test_pending_takes_the_upstream_before_origin_main(unpushed, repo, git, ws_config, capsys):
    git(repo, "remote", "add", "origin", str(repo))
    git(repo, "update-ref", "refs/remotes/origin/other", unpushed)
    git(repo, "branch", "--set-upstream-to=origin/other")
    assert main(["names", "pending"]) == 0
    assert capsys.readouterr().out == ""


def test_pending_without_any_remote_state_lists_everything_unpushed(
    repo, git, monkeypatch, capsys, ws_config
):
    commit(repo, git, "feat: x", {"notes.md": "Zorblax\n"})
    monkeypatch.chdir(repo)
    assert main(["names", "pending"]) == 0
    assert capsys.readouterr().out.startswith("Zorblax: ")


def test_pending_accepts_a_range_and_a_vocabulary(unpushed, ws_config, capsys):
    assert main(["names", "pending", "--range", f"{unpushed}~1..{unpushed}", "--against", ""]) == 0
    assert capsys.readouterr().out.count("\n") == 3
    assert (
        main(["names", "pending", "--range", f"{unpushed}~1..{unpushed}", "--against", unpushed])
        == 0
    )
    assert capsys.readouterr().out == ""


def test_pending_without_a_names_table_exits_2(unpushed, tmp_path, monkeypatch, capsys):
    monkeypatch.setenv("WS_CONFIG_DIR", str(tmp_path / "no-config"))
    assert main(["names", "pending"]) == 2
    assert "names table not found" in capsys.readouterr().err


def test_check_staged_blocks_by_default_and_warns_with_the_flag(
    repo, git, monkeypatch, ws_config, capsys
):
    commit(repo, git, "base", {"a.md": "fine\n"})
    (repo / "a.md").write_text("fine\nZorblax\n", encoding="utf-8")
    git(repo, "add", "a.md")
    monkeypatch.chdir(repo)
    assert main(["names", "check", "--staged", "--against", "HEAD"]) == 1
    captured = capsys.readouterr()
    assert "Zorblax: a.md:2" in captured.out
    assert "The push is blocked" in captured.out
    assert main(["names", "check", "--staged", "--against", "HEAD", "--warn"]) == 0
    captured = capsys.readouterr()
    assert captured.out == ""
    assert "Zorblax: a.md:2" in captured.err
    assert "The commit goes through" in captured.err


def test_check_message_reads_a_message_file(repo, git, tmp_path, monkeypatch, ws_config, capsys):
    commit(repo, git, "base", {"a.md": "fine\n"})
    message = tmp_path / "msg.txt"
    message.write_text("fix: x\n\nQuuxmark\n# Zorblax\n", encoding="utf-8")
    monkeypatch.chdir(repo)
    assert main(["names", "check", "--message", str(message), "--against", "HEAD"]) == 1
    out = capsys.readouterr().out
    assert "Quuxmark: message:3" in out
    assert "Zorblax" not in out


def test_check_range_takes_the_tip_for_known_words(
    unpushed, repo, git, monkeypatch, ws_config, capsys
):
    tip = commit(repo, git, "chore: x", {".known-words": "Zorblax\nQuuxmark\nFrobnitz\n"})
    args = ["names", "check", "--range", "origin/main..HEAD", "--against", "origin/main"]
    assert main([*args, "--tip", tip]) == 0
    assert main([*args, "--tip", unpushed]) == 1
    assert "3 new word(s)" in capsys.readouterr().out


def test_check_needs_one_mode():
    with pytest.raises(SystemExit) as error:
        main(["names", "check"])
    assert error.value.code == 2


def test_check_fails_closed_without_a_names_table_and_never_blocks_when_warning(
    repo, tmp_path, monkeypatch, capsys
):
    monkeypatch.setenv("WS_CONFIG_DIR", str(tmp_path / "no-config"))
    monkeypatch.chdir(repo)
    assert main(["names", "check", "--staged"]) == 1
    assert "names table not found" in capsys.readouterr().err
    assert main(["names", "check", "--staged", "--warn"]) == 0
    assert "not blocking" in capsys.readouterr().err


def test_check_fails_closed_on_a_bad_revision(unpushed, ws_config, capsys):
    assert main(["names", "check", "--range", "origin/main..HEAD", "--against", "no-such-rev"]) == 1
    assert "blocking" in capsys.readouterr().err


def test_known_creates_the_file_and_does_not_repeat_a_word(repo, monkeypatch, capsys, ws_config):
    monkeypatch.chdir(repo)
    assert main(["names", "known", "Celery", "Datadog"]) == 0
    assert "added to .known-words: Celery, Datadog" in capsys.readouterr().out
    assert main(["names", "known", "CELERY", "Flower"]) == 0
    out = capsys.readouterr().out
    assert "added to .known-words: Flower" in out
    assert "already listed: CELERY" in out
    lines = (repo / ".known-words").read_text(encoding="utf-8").splitlines()
    assert [line for line in lines if not line.startswith("#") and line] == [
        "Celery",
        "Datadog",
        "Flower",
    ]


def test_known_refuses_something_that_is_not_a_word(repo, monkeypatch, capsys, ws_config):
    monkeypatch.chdir(repo)
    assert main(["names", "known", "Celery", "two words"]) == 2
    assert "not a single word" in capsys.readouterr().err
    assert not (repo / ".known-words").exists()


def test_known_outside_a_repo_exits_2(tmp_path, monkeypatch, capsys, ws_config):
    monkeypatch.chdir(tmp_path)
    assert main(["names", "known", "Celery"]) == 2
    assert "ws names known" in capsys.readouterr().err


def test_add_appends_an_entry_and_keeps_the_rest_and_the_mode(ws_config, capsys):
    path = ws_config / "names.toml"
    path.chmod(0o600)
    before = path.read_text(encoding="utf-8")
    assert main(["names", "add", "Zorblax Group", "--analog", "Zeta Group"]) == 0
    assert "Zorblax Group" in capsys.readouterr().out
    assert path.read_text(encoding="utf-8").startswith(before)
    assert stat.S_IMODE(path.stat().st_mode) == 0o600
    added = load_names(path).names[-1]
    assert (added.real, added.analog, added.case_sensitive) == (
        "Zorblax Group",
        "Zeta Group",
        False,
    )
    assert len(load_names(path).names) == 5


def test_add_can_be_case_sensitive(ws_config):
    assert main(["names", "add", "Orbit", "--analog", "Loop", "--case-sensitive"]) == 0
    assert load_names(ws_config / "names.toml").names[-1].case_sensitive is True


def test_add_escapes_what_toml_needs(ws_config):
    assert main(["names", "add", 'Zor"blax \\ Co', "--analog", "Zeta"]) == 0
    assert load_names(ws_config / "names.toml").names[-1].real == 'Zor"blax \\ Co'


def test_add_to_a_file_without_a_final_newline(ws_config):
    path = ws_config / "names.toml"
    path.write_text('[[names]]\nreal = "Acme"\nanalog = "Apex"', encoding="utf-8")
    assert main(["names", "add", "Zorblax", "--analog", "Zeta"]) == 0
    assert [name.real for name in load_names(path).names] == ["Acme", "Zorblax"]


@pytest.mark.parametrize(
    ("real", "analog", "message"),
    [
        ("acme", "Other", "already in the table"),
        ("ACME CORP", "Other", "already in the table"),
        ("Meridia", "Other", "already in the table"),
        ("Apex", "Other", "analog of an existing entry"),
        ("Zorblax", "zorblax", "must differ"),
        ("Zorblax", " ", "both needed"),
    ],
)
def test_add_refuses_a_duplicate_or_a_bad_entry(ws_config, capsys, real, analog, message):
    path = ws_config / "names.toml"
    before = path.read_text(encoding="utf-8")
    exit_code = main(["names", "add", real, "--analog", analog])
    assert (exit_code, message in capsys.readouterr().err) == (2, True), real
    assert path.read_text(encoding="utf-8") == before


def test_add_without_a_names_table_does_not_create_one(tmp_path, monkeypatch, capsys):
    monkeypatch.setenv("WS_CONFIG_DIR", str(tmp_path / "empty"))
    assert main(["names", "add", "Zorblax", "--analog", "Zeta"]) == 2
    assert "names table not found" in capsys.readouterr().err
    assert not (tmp_path / "empty").exists()


def test_add_requires_an_analog():
    with pytest.raises(SystemExit) as error:
        main(["names", "add", "Zorblax"])
    assert error.value.code == 2


def test_review_answers_each_word(unpushed, repo, git, ws_config, monkeypatch, capsys):
    (repo / "extra.md").write_text("another Zorblax line\n", encoding="utf-8")
    git(repo, "add", "extra.md")
    stdin(monkeypatch, "r\nZeta Group\nh\ns\n")
    assert main(["names", "review"]) == 0
    out = capsys.readouterr().out
    added = load_names(ws_config / "names.toml").names[-1]
    assert (added.real, added.analog) == ("Zorblax", "Zeta Group")
    known = (repo / ".known-words").read_text(encoding="utf-8")
    assert known.endswith("\nQuuxmark\n")
    assert "Frobnitz" not in known
    assert "1 real name(s), 1 harmless word(s), 1 skipped." in out
    assert "Commit .known-words" in out
    work_tree, commits = out.split("Unpushed commits")
    assert "  notes.md:1" in work_tree
    assert "  extra.md:1" in work_tree
    assert f"  {unpushed[:10]} message:1" in commits
    assert f"  {unpushed[:10]} notes.md:1" in commits
    assert "ws mask --in-place" in work_tree
    assert "Quuxmark" not in commits


def test_review_only_reports_the_real_names_it_added(unpushed, ws_config, monkeypatch, capsys):
    stdin(monkeypatch, "h\nh\nh\n")
    assert main(["names", "review"]) == 0
    out = capsys.readouterr().out
    assert "0 real name(s), 3 harmless word(s), 0 skipped." in out
    assert "Work-tree files" not in out


def test_review_with_nothing_pending(repo, git, monkeypatch, ws_config, capsys):
    base = commit(repo, git, "base", {"a.md": "fine\n"})
    git(repo, "update-ref", "refs/remotes/origin/main", base)
    monkeypatch.chdir(repo)
    assert main(["names", "review"]) == 0
    assert capsys.readouterr().out == "no pending new words\n"


def test_review_quit_leaves_the_rest_unanswered(unpushed, repo, ws_config, monkeypatch, capsys):
    stdin(monkeypatch, "h\nq\n")
    assert main(["names", "review"]) == 0
    assert "0 real name(s), 1 harmless word(s), 2 skipped." in capsys.readouterr().out
    assert (repo / ".known-words").read_text(encoding="utf-8").endswith("\nZorblax\n")


def test_review_treats_the_end_of_the_input_as_quit(unpushed, repo, ws_config, monkeypatch, capsys):
    stdin(monkeypatch, "")
    assert main(["names", "review"]) == 0
    assert "0 real name(s), 0 harmless word(s), 3 skipped." in capsys.readouterr().out
    assert not (repo / ".known-words").exists()


def test_review_asks_again_after_an_unknown_answer_and_an_empty_one_skips(
    unpushed, ws_config, monkeypatch, capsys
):
    stdin(monkeypatch, "x\n\nh\ns\n")
    assert main(["names", "review"]) == 0
    out = capsys.readouterr().out
    assert "answer r, h, s or q" in out
    assert "0 real name(s), 1 harmless word(s), 2 skipped." in out


def test_review_skips_a_real_name_without_analog_or_refused(
    unpushed, ws_config, monkeypatch, capsys
):
    before = (ws_config / "names.toml").read_text(encoding="utf-8")
    stdin(monkeypatch, "r\n\nr\nquuxmark\nq\n")
    assert main(["names", "review"]) == 0
    out = capsys.readouterr().out
    assert "no analog given: skipped" in out
    assert "refused: the analog must differ from the real name" in out
    assert (ws_config / "names.toml").read_text(encoding="utf-8") == before


def test_review_without_a_names_table_exits_2(unpushed, tmp_path, monkeypatch, capsys):
    monkeypatch.setenv("WS_CONFIG_DIR", str(tmp_path / "no-config"))
    assert main(["names", "review"]) == 2
    assert "names table not found" in capsys.readouterr().err
