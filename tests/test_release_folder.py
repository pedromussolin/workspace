import hashlib
from datetime import date

import pytest

from ws.release import ReleaseRefused, ReleaseSetup, folder

SITE = "https://example.atlassian.net"


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
        'repo-a = ["feature/TS-101-one", "feature/TS-102-two"]\n',
    )
    release = folder.read_release(tmp_path, ("repo-a", "repo-b"))
    assert release.repos == ("repo-a", "repo-b")
    assert release.include == {"repo-a": ("feature/TS-101-one", "feature/TS-102-two")}


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
    drafts = folder.pr_drafts(tmp_path, "repo-a")
    assert set(drafts) == {"code", "sandbox", "sandbox-2"}
    assert drafts["sandbox-2"].path.name == "repo-a-sandbox-2.md"
    assert folder.pr_drafts(tmp_path, "repo-z") == {}


def test_render_tasks_and_date():
    text = folder.render(
        "{tasks}\n{release_date}",
        tasks=("TS-101", "TS-102"),
        site=SITE,
        day=date(2026, 11, 20),
        known={},
    )
    assert text == f"- TS-101: {SITE}/browse/TS-101\n- TS-102: {SITE}/browse/TS-102\n20/11/2026"
    assert folder.release_line(date(2026, 11, 20)) == "Release: 20/11/2026"


def test_render_keeps_unknown_refs():
    known = {"repo-b": ("acme/repo-b#5", "https://github.com/acme/repo-b/pull/5", 5)}
    text = "{pr:repo-b} {url:repo-b} {num:repo-b} {pr:repo-a-sandbox}"
    out = folder.render(text, tasks=("TS-1",), site=SITE, day=date(2026, 11, 20), known=known)
    assert out == ("acme/repo-b#5 https://github.com/acme/repo-b/pull/5 5 {pr:repo-a-sandbox}")
    assert folder.pending_refs(out) == ["repo-a-sandbox"]
    assert folder.resolve_refs("{num:repo-b}", known) == "5"


def test_bad_placeholders():
    text = "{pr:repo-c} {prs:repo-a} {tasks} {pr:repo-a} {release_date}"
    assert folder.bad_placeholders(text, {"repo-a"}) == ["{pr:repo-c}", "{prs:repo-a}"]
