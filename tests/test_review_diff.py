import os
import subprocess
from pathlib import Path

import pytest

from ws import reviewdiff
from ws.reviewdiff import Checkout, Commit, ReviewRefused

BRANCH = "feature/TS-5-fechar-lote"


@pytest.fixture(autouse=True)
def isolated_env(monkeypatch):
    monkeypatch.setenv("GIT_CONFIG_GLOBAL", os.devnull)
    monkeypatch.setenv("GIT_CONFIG_NOSYSTEM", "1")


def git(repo: Path, *args: str) -> str:
    result = subprocess.run(["git", *args], cwd=repo, capture_output=True, text=True, check=True)
    return result.stdout.strip()


def write(repo: Path, name: str, content: str | bytes) -> None:
    path = repo / name
    path.parent.mkdir(parents=True, exist_ok=True)
    if isinstance(content, bytes):
        path.write_bytes(content)
    else:
        path.write_text(content, encoding="utf-8")


def commit(repo: Path, message: str, **files: str | bytes) -> None:
    for name, content in files.items():
        write(repo, name, content)
    git(repo, "add", "-A")
    git(repo, "commit", "-q", "-m", message)


def configure(repo: Path) -> None:
    git(repo, "config", "user.name", "Test")
    git(repo, "config", "user.email", "test@example.com")
    git(repo, "config", "commit.gpgsign", "false")


@pytest.fixture
def clone(tmp_path) -> Path:
    origin = tmp_path / "origin.git"
    subprocess.run(["git", "init", "-q", "--bare", "-b", "master", str(origin)], check=True)
    path = tmp_path / "acme-api"
    subprocess.run(["git", "clone", "-q", str(origin), str(path)], check=True, capture_output=True)
    configure(path)
    git(path, "switch", "-q", "-c", "master")
    commit(path, "chore: base", **{"base.txt": "base\n"})
    git(path, "push", "-q", "origin", "master")
    git(path, "fetch", "-q", "origin")
    git(path, "switch", "-q", "--no-track", "-c", BRANCH, "master")
    return path


def files_by_path(collected):
    return {change.path: change for change in collected.files}


def test_find_checkout_current_branch(clone):
    assert reviewdiff.find_checkout(clone, "TS-5") == Checkout(BRANCH, clone)


def test_find_checkout_branch_in_another_worktree(clone, tmp_path):
    git(clone, "switch", "-q", "master")
    other = tmp_path / "linked"
    git(clone, "worktree", "add", "-q", str(other), BRANCH)
    found = reviewdiff.find_checkout(clone, "TS-5")
    assert found.branch == BRANCH
    assert found.worktree is not None
    assert found.worktree.resolve() == other.resolve()


def test_find_checkout_branch_checked_out_nowhere(clone):
    git(clone, "switch", "-q", "master")
    assert reviewdiff.find_checkout(clone, "TS-5") == Checkout(BRANCH, None)


def test_find_checkout_refuses_a_worktree_that_is_gone(clone, tmp_path):
    git(clone, "switch", "-q", "master")
    other = tmp_path / "linked"
    git(clone, "worktree", "add", "-q", str(other), BRANCH)
    other.rename(tmp_path / "moved")
    with pytest.raises(ReviewRefused) as error:
        reviewdiff.find_checkout(clone, "TS-5")
    assert f"{BRANCH} is checked out in " in str(error.value)
    assert f"git -C {clone} worktree prune" in str(error.value)


def test_find_checkout_refuses_none_and_two(clone):
    git(clone, "switch", "-q", "master")
    git(clone, "branch", "-q", "-D", BRANCH)
    git(clone, "branch", "feature/TS-5-x-sdbx", "master")
    with pytest.raises(ReviewRefused) as none:
        reviewdiff.find_checkout(clone, "TS-5")
    assert str(none.value) == "no task branch for TS-5 in acme-api; run ws card start TS-5"
    git(clone, "branch", BRANCH, "master")
    git(clone, "branch", "fix/TS-5-outra", "master")
    git(clone, "branch", "hotfix/TS-5-mais", "master")
    with pytest.raises(ReviewRefused) as two:
        reviewdiff.find_checkout(clone, "TS-5")
    assert str(two.value) == (
        "TS-5 has more than one task branch in acme-api: "
        f"{BRANCH}, fix/TS-5-outra, hotfix/TS-5-mais"
    )


def test_collect_committed_staged_unstaged_and_untracked(clone):
    commit(clone, "feat: a", **{"a.py": "one\ntwo\n"})
    write(clone, "a.py", "one\ntwo\nthree\n")
    write(clone, "b.py", "x\ny\n")
    git(clone, "add", "b.py")
    write(clone, "c.py", "only\n")
    checkout = reviewdiff.find_checkout(clone, "TS-5")
    collected = reviewdiff.collect(clone, checkout, "master")
    changes = files_by_path(collected)
    assert [change.path for change in collected.files] == ["a.py", "b.py", "c.py"]
    assert changes["a.py"].stages == ("committed", "unstaged")
    assert (changes["a.py"].added, changes["a.py"].deleted) == (3, 0)
    assert changes["a.py"].status == "added"
    assert changes["b.py"].stages == ("staged",)
    assert (changes["b.py"].added, changes["b.py"].deleted) == (2, 0)
    assert changes["c.py"].stages == ("untracked",)
    assert changes["c.py"].status == "added"
    assert (changes["c.py"].added, changes["c.py"].deleted) == (1, 0)
    assert changes["c.py"].hunks == (1,)
    assert collected.merge_base == git(clone, "rev-parse", "master")


def test_collect_compares_with_the_merge_base(clone, tmp_path):
    commit(clone, "feat: a", **{"a.py": "a\n"})
    other = tmp_path / "other"
    subprocess.run(
        ["git", "clone", "-q", str(tmp_path / "origin.git"), str(other)],
        check=True,
        capture_output=True,
    )
    configure(other)
    commit(other, "feat: later", **{"later.py": "l\n"})
    git(other, "push", "-q", "origin", "HEAD:master")
    git(clone, "fetch", "-q", "origin")
    collected = reviewdiff.collect(clone, reviewdiff.find_checkout(clone, "TS-5"), "master")
    assert [change.path for change in collected.files] == ["a.py"]
    assert [commit.subject for commit in collected.commits] == ["feat: a"]


def test_collect_rename_keeps_the_old_path(clone):
    body = "".join(f"line {n}\n" for n in range(1, 21))
    commit(clone, "feat: x", **{"x.py": body})
    git(clone, "push", "-q", "origin", f"{BRANCH}:master")
    git(clone, "fetch", "-q", "origin")
    git(clone, "mv", "x.py", "y.py")
    write(clone, "y.py", body.replace("line 5\n", "line five\n"))
    git(clone, "add", "-A")
    git(clone, "commit", "-q", "-m", "refact: move")
    collected = reviewdiff.collect(clone, reviewdiff.find_checkout(clone, "TS-5"), "master")
    [change] = collected.files
    assert (change.path, change.old_path, change.status) == ("y.py", "x.py", "renamed")
    assert (change.added, change.deleted) == (1, 1)
    assert change.hunks == (5,)


def test_collect_binary_files(clone):
    commit(clone, "feat: bin", **{"img.bin": b"\x00\x01\x02"})
    write(clone, "new.bin", b"ab\x00cd")
    collected = reviewdiff.collect(clone, reviewdiff.find_checkout(clone, "TS-5"), "master")
    changes = files_by_path(collected)
    for name in ("img.bin", "new.bin"):
        assert changes[name].binary is True
        assert changes[name].added is None
        assert changes[name].deleted is None
        assert changes[name].hunks == ()
    assert changes["new.bin"].stages == ("untracked",)


def test_collect_hunks_are_new_side_lines(clone):
    body = "".join(f"line {n}\n" for n in range(1, 13))
    commit(clone, "feat: f", **{"f.txt": body})
    git(clone, "push", "-q", "origin", f"{BRANCH}:master")
    git(clone, "fetch", "-q", "origin")
    changed = body.replace("line 3\n", "three\n").replace("line 10\n", "ten\n")
    write(clone, "f.txt", changed)
    collected = reviewdiff.collect(clone, reviewdiff.find_checkout(clone, "TS-5"), "master")
    [change] = collected.files
    assert change.status == "modified"
    assert change.hunks == (3, 10)


def test_collect_hunks_are_capped(clone):
    body = "".join(f"line {n}\n" for n in range(1, 101))
    commit(clone, "feat: f", **{"f.txt": body})
    git(clone, "push", "-q", "origin", f"{BRANCH}:master")
    git(clone, "fetch", "-q", "origin")
    lines = body.splitlines(keepends=True)
    for index in range(1, 100, 3):
        lines[index] = "changed\n"
    write(clone, "f.txt", "".join(lines))
    [change] = reviewdiff.collect(clone, reviewdiff.find_checkout(clone, "TS-5"), "master").files
    assert len(change.hunks) == reviewdiff.MAX_BLOCKS


def test_collect_reverted_file_is_not_listed(clone):
    commit(clone, "feat: a", **{"a.py": "a\n"})
    git(clone, "rm", "-q", "-f", "a.py")
    collected = reviewdiff.collect(clone, reviewdiff.find_checkout(clone, "TS-5"), "master")
    assert collected.files == ()


def test_collect_deleted_file(clone):
    git(clone, "rm", "-q", "base.txt")
    git(clone, "commit", "-q", "-m", "chore: remove")
    [change] = reviewdiff.collect(clone, reviewdiff.find_checkout(clone, "TS-5"), "master").files
    assert (change.status, change.path, change.deleted) == ("deleted", "base.txt", 1)


def test_collect_paths_with_spaces_and_non_ascii(clone):
    commit(clone, "feat: p", **{"pasta com espaço/ação.py": "a\n"})
    write(clone, "outra pasta/novo é.py", "n\n")
    collected = reviewdiff.collect(clone, reviewdiff.find_checkout(clone, "TS-5"), "master")
    changes = files_by_path(collected)
    assert set(changes) == {"pasta com espaço/ação.py", "outra pasta/novo é.py"}
    assert changes["pasta com espaço/ação.py"].hunks == (1,)
    assert changes["pasta com espaço/ação.py"].stages == ("committed",)
    assert changes["outra pasta/novo é.py"].stages == ("untracked",)


def test_collect_reads_the_branch_worktree_not_the_main_checkout(clone, tmp_path):
    commit(clone, "feat: a", **{"a.py": "a\n"})
    git(clone, "switch", "-q", "master")
    other = tmp_path / "linked"
    git(clone, "worktree", "add", "-q", str(other), BRANCH)
    write(clone, "unrelated.py", "u\n")
    write(other, "a.py", "a\nb\n")
    checkout = reviewdiff.find_checkout(clone, "TS-5")
    collected = reviewdiff.collect(clone, checkout, "master")
    assert [change.path for change in collected.files] == ["a.py"]
    assert collected.files[0].stages == ("committed", "unstaged")


def test_collect_without_worktree_reads_commits_only(clone):
    commit(clone, "feat: a", **{"a.py": "a\n"})
    git(clone, "switch", "-q", "master")
    write(clone, "unrelated.py", "u\n")
    collected = reviewdiff.collect(clone, Checkout(BRANCH, None), "master")
    [change] = collected.files
    assert (change.path, change.stages) == ("a.py", ("committed",))
    assert collected.commits == (Commit(git(clone, "rev-parse", BRANCH), "feat: a"),)


def test_collect_commits_oldest_first(clone):
    commit(clone, "feat: one", **{"a.py": "1\n"})
    commit(clone, "feat: two", **{"a.py": "2\n"})
    collected = reviewdiff.collect(clone, reviewdiff.find_checkout(clone, "TS-5"), "master")
    assert [commit.subject for commit in collected.commits] == ["feat: one", "feat: two"]


def test_diff_command_quotes_paths(tmp_path):
    repo = tmp_path / "my repo"
    worktree = tmp_path / "my tree"
    assert reviewdiff.diff_command(repo, Checkout("b", worktree), "abc") == (
        f"git -C '{worktree}' diff -M abc"
    )
    assert reviewdiff.diff_command(repo, Checkout("b", None), "abc") == (
        f"git -C '{repo}' diff -M abc b"
    )


def test_collect_big_untracked_file_is_read_in_chunks(clone, monkeypatch):
    sizes = []
    real_open = open

    class Spy:
        def __init__(self, handle):
            self.handle = handle

        def __enter__(self):
            return self

        def __exit__(self, *exc):
            self.handle.close()

        def read(self, size=-1):
            sizes.append(size)
            return self.handle.read(size)

    monkeypatch.setattr(reviewdiff, "open", lambda *a, **k: Spy(real_open(*a, **k)), raising=False)
    write(clone, "big.txt", "linha\n" * 700_000 + "sem fim")
    [change] = reviewdiff.collect(clone, Checkout(BRANCH, clone), "master").files
    assert (change.added, change.binary) == (700_001, False)
    assert sizes
    assert all(0 < size <= reviewdiff.CHUNK_BYTES for size in sizes)


def test_collect_untracked_edge_entries(clone, tmp_path):
    write(clone, "empty.txt", "")
    (clone / "link").symlink_to(tmp_path)
    nested = clone / "nested"
    nested.mkdir()
    subprocess.run(["git", "init", "-q", str(nested)], check=True)
    configure(nested)
    commit(nested, "x", **{"f": "f\n"})
    changes = files_by_path(reviewdiff.collect(clone, Checkout(BRANCH, clone), "master"))
    assert (changes["empty.txt"].added, changes["empty.txt"].hunks) == (0, ())
    assert (changes["link"].added, changes["link"].hunks) == (1, (1,))
    assert changes["nested/"].binary is True
    assert changes["nested/"].added is None


def test_collect_ignored_folder_is_not_listed(clone):
    commit(clone, "chore: ignore", **{".gitignore": "build/\n"})
    write(clone, "build/out.py", "o\n")
    paths = [c.path for c in reviewdiff.collect(clone, Checkout(BRANCH, clone), "master").files]
    assert paths == [".gitignore"]


def test_collect_path_with_a_newline(clone):
    write(clone, "a\nb.py", "x\n")
    commit(clone, "feat: n", **{"c\nd.py": "y\n"})
    paths = {c.path for c in reviewdiff.collect(clone, Checkout(BRANCH, clone), "master").files}
    assert paths == {"a\nb.py", "c\nd.py"}


def test_collect_refuses_a_missing_base(clone):
    with pytest.raises(ReviewRefused) as error:
        reviewdiff.collect(clone, Checkout(BRANCH, clone), "nope")
    assert str(error.value) == "origin/nope not found; fetch first"


def test_collect_refuses_no_common_ancestor(clone):
    git(clone, "switch", "-q", "--orphan", "feature/TS-9-orfa")
    commit(clone, "feat: orphan", **{"o.txt": "o\n"})
    with pytest.raises(ReviewRefused) as error:
        reviewdiff.collect(clone, Checkout("feature/TS-9-orfa", clone), "master")
    assert str(error.value) == "no common ancestor between feature/TS-9-orfa and origin/master"
