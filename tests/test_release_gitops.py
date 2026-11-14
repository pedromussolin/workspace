import subprocess

import pytest
from release_helpers import REV_BASE, World

from ws.release import gitops

pytest_plugins = ["release_helpers"]


def test_merge_tree_clean_gives_a_tree_and_sources_at_reads_it(world: World):
    repo = world.clone("repo-a")
    tree, conflicts = gitops.merge_tree(repo, "feature/TS-101-one", "origin/sandbox")
    assert conflicts == []
    assert tree and len(tree) >= 40
    sources = gitops.sources_at(repo, tree, "migrations/versions")
    assert set(sources) == {"0001_base.py"}
    assert REV_BASE in sources["0001_base.py"]


def test_merge_tree_conflict_lists_files(world: World):
    world.commit("repo-a", "feature/TS-101-one", "shared.txt", "one\n", "feat: shared")
    world.commit("repo-a", "sandbox", "shared.txt", "sandbox\n", "chore: shared")
    tree, conflicts = gitops.merge_tree(world.clone("repo-a"), "feature/TS-101-one", "sandbox")
    assert tree is None
    assert conflicts == ["shared.txt"]


def test_add_worktree_new_branch_has_no_upstream(world: World, tmp_path):
    repo = world.clone("repo-a")
    path = tmp_path / "wt"
    gitops.add_worktree(repo, path, "release/20261120", "origin/master")
    assert (path / "migrations" / "versions" / "0001_base.py").exists()
    assert gitops.upstream(repo, "release/20261120") is None
    assert gitops.upstream(repo, "feature/TS-101-one") is None
    world.git("repo-a", "branch", "--set-upstream-to=origin/master", "master")
    assert gitops.upstream(repo, "master") == "origin/master"


def test_merge_conflict_stays_in_progress(world: World, tmp_path):
    world.commit("repo-a", "feature/TS-101-one", "shared.txt", "one\n", "feat: shared")
    world.commit("repo-a", "feature/TS-102-two", "shared.txt", "two\n", "feat: shared")
    repo = world.clone("repo-a")
    path = tmp_path / "wt"
    gitops.add_worktree(repo, path, "release/20261120", "origin/feature/TS-101-one")
    assert gitops.clean(path)
    assert not gitops.merging(path)
    files = gitops.merge(path, "origin/feature/TS-102-two", "feat(TS-102): junta")
    assert files == ["shared.txt"]
    assert gitops.merging(path)
    assert not gitops.clean(path)


def test_merge_clean_makes_a_merge_commit_with_the_message(world: World, tmp_path):
    repo = world.clone("repo-a")
    path = tmp_path / "wt"
    gitops.add_worktree(repo, path, "release/20261120", "origin/feature/TS-101-one")
    assert gitops.merge(path, "origin/feature/TS-102-two", "feat(TS-102): junta", "corpo") == []
    head = gitops.rev(path, "HEAD")
    assert head
    text = gitops.message(path, head)
    assert text.startswith("feat(TS-102): junta")
    assert "corpo" in text
    assert len(gitops.commits(path, "origin/master..HEAD", merges=True)) == 1


def test_checked_out_at_finds_the_clone(world: World, tmp_path):
    repo = world.clone("repo-a")
    assert gitops.checked_out_at(repo, "master") == repo.resolve()
    assert gitops.checked_out_at(repo, "feature/TS-101-one") is None
    path = tmp_path / "wt"
    gitops.add_worktree(repo, path, "release/20261120", "origin/master")
    assert gitops.checked_out_at(repo, "release/20261120") == path.resolve()
    gitops.add_worktree(repo, tmp_path / "wt2", "feature/TS-101-one")
    assert gitops.checked_out_at(repo, "feature/TS-101-one") == (tmp_path / "wt2").resolve()


def test_fetch_failure_is_text(world: World, tmp_path):
    repo = world.clone("repo-a")
    assert gitops.fetch(repo) is None
    world.git("repo-a", "remote", "set-url", "origin", str(tmp_path / "missing"))
    error = gitops.fetch(repo)
    assert isinstance(error, str)
    assert error


def test_branches_with_uses_the_key_boundary(world: World):
    repo = world.clone("repo-a")
    assert gitops.branches_with(repo, "TS-10") == ([], [])
    local, remote = gitops.branches_with(repo, "TS-101")
    assert local == ["feature/TS-101-one"]
    assert remote == ["origin/feature/TS-101-one"]


def test_commits_first_parent_merges(world: World, tmp_path):
    repo = world.clone("repo-a")
    path = tmp_path / "wt"
    gitops.add_worktree(repo, path, "release/20261120", "origin/master")
    gitops.merge(path, "origin/feature/TS-101-one", "feat(TS-101): um")
    gitops.merge(path, "origin/feature/TS-102-two", "feat(TS-102): dois")
    spec = "origin/master..release/20261120"
    merges = gitops.commits(repo, spec, merges=True, first_parent=True)
    assert [subject for _, subject in merges] == ["feat(TS-101): um", "feat(TS-102): dois"]
    assert len(gitops.commits(repo, spec)) == 4
    assert [s for _, s in gitops.commits(repo, spec, merges=False)] == [
        "feat: one.txt",
        "feat: two.txt",
    ]
    assert gitops.count(repo, spec) == 4
    assert gitops.is_ancestor(repo, "origin/master", "release/20261120")
    assert not gitops.is_ancestor(repo, "release/20261120", "origin/master")


def test_diff_names_and_read_at(world: World):
    repo = world.clone("repo-a")
    assert gitops.diff_names(repo, "origin/master", "origin/feature/TS-101-one") == ["one.txt"]
    assert gitops.read_at(repo, "origin/master", "one.txt") is None
    assert gitops.read_at(repo, "origin/feature/TS-101-one", "one.txt") == "one.txt\n"
    assert gitops.rev(repo, "nope") is None


def test_git_raises_on_failure_unless_unchecked(world: World):
    repo = world.clone("repo-a")
    with pytest.raises(gitops.GitFailed):
        gitops.git(repo, "rev-parse", "--verify", "nope")
    assert gitops.git(repo, "rev-parse", "--verify", "nope", check=False).returncode != 0


def test_world_env_isolated(world: World):
    out = subprocess.run(
        ["git", "-C", str(world.clone("repo-b")), "config", "--global", "-l"],
        capture_output=True,
        text=True,
    )
    assert out.stdout == ""
    assert set(world.refs("repo-b")) >= {"refs/heads/master", "refs/heads/sandbox"}
