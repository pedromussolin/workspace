import hashlib
from datetime import date

import pytest

from ws.release import ReleaseRefused, ReleaseSetup, folder

SITE = "https://example.atlassian.net"
TEMPLATE = f"{SITE}/browse/{{key}}"


@pytest.fixture
def roots(tmp_path, monkeypatch):
    repo = tmp_path / "repo"
    data = tmp_path / "data"
    (repo / "projects" / "alpha" / "sub").mkdir(parents=True)
    (data / "projects" / "beta").mkdir(parents=True)
    monkeypatch.setenv("WS_REPO_ROOT", str(repo))
    monkeypatch.setenv("WS_DATA_DIR", str(data))
    return repo, data


def test_resolve_slug_explicit_and_from_cwd(roots, tmp_path):
    repo, data = roots
    assert folder.resolve_slug("gamma", tmp_path) == "gamma"
    assert folder.resolve_slug(None, repo / "projects" / "alpha" / "sub") == "alpha"
    assert folder.resolve_slug(None, data / "projects" / "beta") == "beta"
    with pytest.raises(ReleaseSetup, match="--project"):
        folder.resolve_slug(None, tmp_path)


@pytest.mark.parametrize("bad", ["../x", "a/b", "a_b", "-x"])
def test_resolve_slug_refuses_a_project_that_is_not_a_slug(roots, tmp_path, bad):
    with pytest.raises(ReleaseSetup, match="not a project slug"):
        folder.resolve_slug(bad, tmp_path)


def test_release_dir_and_ensure_dir(roots):
    _, data = roots
    path = folder.release_dir("beta", date(2026, 11, 20))
    assert path == data / "projects" / "beta" / "release-20261120"
    assert not path.exists()
    folder.ensure_dir(path)
    assert path.stat().st_mode & 0o777 == 0o700


def write(path, text):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text)
    return path


def test_read_release(tmp_path):
    write(
        tmp_path / "release.toml",
        'repos = ["repo-a", "repo-b"]\n[include]\n'
        'repo-a = ["feature/TS-101-one", "feature/TS-102-two"]\n'
        'repo-b = ["feature/TS-201-only"]\n',
    )
    release = folder.read_release(tmp_path, ("repo-a", "repo-b"))
    assert release.repos == ("repo-a", "repo-b")
    assert release.include == {
        "repo-a": ("feature/TS-101-one", "feature/TS-102-two"),
        "repo-b": ("feature/TS-201-only",),
    }


def test_read_release_missing_is_a_setup_problem(tmp_path):
    with pytest.raises(ReleaseSetup, match="not found"):
        folder.read_release(tmp_path / "absent", ("repo-a",))
    with pytest.raises(ReleaseSetup, match="not found"):
        folder.read_release(tmp_path, ("repo-a",))


def test_read_release_needs_one_include_per_repo_and_no_duplicate(tmp_path):
    write(
        tmp_path / "release.toml",
        'repos = ["repo-a", "repo-b", "repo-a"]\n[include]\nrepo-a = ["feature/TS-1-x"]\n',
    )
    with pytest.raises(ReleaseRefused) as info:
        folder.read_release(tmp_path, ("repo-a", "repo-b"))
    assert "repo repo-a appears twice in repos" in str(info.value)
    assert "repo-b is in repos but has no include list" in str(info.value)


def test_non_utf8_files_are_refused_cleanly(tmp_path):
    (tmp_path / "release.toml").write_bytes(b'repos = ["repo-\xe9"]\n')
    with pytest.raises(ReleaseRefused, match="not UTF-8"):
        folder.read_release(tmp_path, ("repo-a",))
    draft = tmp_path / "pr" / "repo-a.md"
    draft.parent.mkdir()
    draft.write_bytes(b'+++\ntitle = "T\xe9"\ntasks = ["TS-1"]\n+++\n')
    with pytest.raises(ReleaseRefused, match="not UTF-8"):
        folder.read_pr(draft)


class _Entry:
    def __init__(self, name):
        self.name = name


class _Config:
    repos = (_Entry("repo-a"), _Entry("repo-b"), _Entry("repo-c"))


def test_select_repos_follows_the_config_order(tmp_path):
    wanted = folder.ReleaseFile(("repo-c", "repo-a"), {"repo-c": ("x",), "repo-a": ("y",)})
    assert folder.select_repos(_Config(), wanted, []) == ["repo-a", "repo-c"]
    assert folder.select_repos(_Config(), wanted, ["repo-c", "repo-c"]) == ["repo-c"]
    with pytest.raises(ReleaseSetup, match="--repo repo-b: not in release.toml"):
        folder.select_repos(_Config(), wanted, ["repo-b"])


def test_read_release_problems(tmp_path):
    write(
        tmp_path / "release.toml",
        'repos = ["repo-a", "repo-c"]\n[include]\n'
        'repo-b = ["feature/TS-1-x"]\n'
        "repo-a = []\n"
        'repo-c = ["feature/TS-2-a", "feature/TS-2-a", "feature/no-key"]\n',
    )
    with pytest.raises(ReleaseRefused) as info:
        folder.read_release(tmp_path, ("repo-a", "repo-b"))
    message = str(info.value)
    for fragment in ("repo-c", "repo-b", "repo-a", "feature/TS-2-a", "feature/no-key"):
        assert fragment in message


PR = (
    '+++\ntitle = "Release"\ntasks = ["TS-101", "TS-102"]\nlabels = ["release"]\n+++\n'
    "Corpo\n{tasks}\n"
)


def test_read_pr(tmp_path):
    path = write(tmp_path / "pr" / "repo-a.md", PR)
    draft = folder.read_pr(path)
    assert draft.title == "Release"
    assert draft.tasks == ("TS-101", "TS-102")
    assert draft.labels == ("release",)
    assert draft.assignees == ()
    assert draft.body == "Corpo\n{tasks}\n"
    assert draft.sha256 == hashlib.sha256(PR.encode()).hexdigest()
    assert draft.path == path


def test_read_pr_refuses_unknown_keys_and_missing_title(tmp_path):
    bad = write(tmp_path / "a.md", '+++\ntitle = "x"\ntasks = ["TS-1"]\nfoo = 1\n+++\nb\n')
    with pytest.raises(ReleaseRefused, match="foo"):
        folder.read_pr(bad)
    no_title = write(tmp_path / "b.md", '+++\ntasks = ["TS-1"]\n+++\nb\n')
    with pytest.raises(ReleaseRefused, match="title"):
        folder.read_pr(no_title)
    no_tasks = write(tmp_path / "c.md", '+++\ntitle = "x"\ntasks = []\n+++\nb\n')
    with pytest.raises(ReleaseRefused, match="tasks"):
        folder.read_pr(no_tasks)
    bad_key = write(tmp_path / "d.md", '+++\ntitle = "x"\ntasks = ["abc"]\n+++\nb\n')
    with pytest.raises(ReleaseRefused, match="abc"):
        folder.read_pr(bad_key)
    no_front = write(tmp_path / "e.md", "just text\n")
    with pytest.raises(ReleaseRefused):
        folder.read_pr(no_front)


def test_pr_drafts_names(tmp_path):
    for name in ("repo-a.md", "repo-a-sandbox.md", "repo-a-sandbox-2.md", "repo-b.md"):
        write(tmp_path / "pr" / name, PR)
    drafts = folder.pr_drafts(tmp_path, "repo-a", ["sandbox", "staging"])
    assert set(drafts) == {"code", "sandbox", "sandbox-2"}
    assert drafts["sandbox-2"].path.name == "repo-a-sandbox-2.md"
    assert folder.pr_drafts(tmp_path, "repo-z", ["sandbox"]) == {}


def test_pr_drafts_name_each_configured_environment(tmp_path):
    for name in ("repo-a-staging.md", "repo-a-staging-3.md", "repo-a-qa.md", "repo-a-staging-1.md"):
        write(tmp_path / "pr" / name, PR)
    drafts = folder.pr_drafts(tmp_path, "repo-a", ["sandbox", "staging"])
    assert set(drafts) == {"staging", "staging-3"}


def test_render_tasks_and_date():
    text = folder.render(
        "{tasks}\n{release_date}",
        tasks=("TS-101", "TS-102"),
        template=TEMPLATE,
        day=date(2026, 11, 20),
        known={},
    )
    assert text == f"- TS-101: {SITE}/browse/TS-101\n- TS-102: {SITE}/browse/TS-102\n20/11/2026"
    assert folder.release_line(date(2026, 11, 20)) == "Release: 20/11/2026"


def test_release_links_use_the_tracker_template():
    other = "https://tasks.example.com/item/{key}"

    assert folder.tasks_block(("TS-7", "TS-8"), other) == (
        "- TS-7: https://tasks.example.com/item/TS-7\n- TS-8: https://tasks.example.com/item/TS-8"
    )


def test_render_keeps_unknown_refs():
    known = {"repo-b": ("acme/repo-b#5", "https://github.com/acme/repo-b/pull/5", 5)}
    text = "{pr:repo-b} {url:repo-b} {num:repo-b} {pr:repo-a-sandbox}"
    out = folder.render(
        text, tasks=("TS-1",), template=TEMPLATE, day=date(2026, 11, 20), known=known
    )
    assert out == ("acme/repo-b#5 https://github.com/acme/repo-b/pull/5 5 {pr:repo-a-sandbox}")
    assert folder.pending_refs(out) == ["repo-a-sandbox"]
    assert folder.resolve_refs("{num:repo-b}", known) == "5"


def test_bad_placeholders():
    text = "{pr:repo-c} {prs:repo-a} {tasks} {pr:repo-a} {release_date}"
    assert folder.bad_placeholders(text, {"repo-a"}) == ["{pr:repo-c}", "{prs:repo-a}"]
