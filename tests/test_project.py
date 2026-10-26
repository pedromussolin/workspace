import shutil
from datetime import date
from pathlib import Path

import pytest

from ws import config
from ws.cli import main
from ws.project import new_project

REPO = Path(__file__).resolve().parents[1]
TEMPLATE = REPO / "templates" / "project"
TODAY = date(2026, 10, 22)


@pytest.fixture
def root(tmp_path: Path) -> Path:
    shutil.copytree(TEMPLATE, tmp_path / "templates" / "project")
    return tmp_path


def test_creates_from_template(root: Path):
    target = new_project("acme-onboarding", root, TODAY)

    assert target == root / "projects" / "acme-onboarding"
    for name in ("README.md", "CLAUDE.md", "CONTINUE.md", "decisions.md"):
        assert (target / name).is_file()
    for folder in ("tasks", "evidence", "attachments"):
        assert (target / folder / ".gitkeep").is_file()

    for md in target.rglob("*.md"):
        text = md.read_text(encoding="utf-8")
        assert "{{" not in text, md.name
        assert text.startswith("Status: rascunho\nData: 22/10/2026\nTags:\n\n"), md.name
    assert "~/.config/workspace/private/acme-onboarding.md" in (target / "CLAUDE.md").read_text(
        encoding="utf-8"
    )


def test_copies_other_files_as_they_are(root: Path):
    (root / "templates" / "project" / "attachments" / "modelo.txt").write_text("{{slug}}\n")

    target = new_project("acme-onboarding", root, TODAY)

    assert (target / "attachments" / "modelo.txt").read_text() == "{{slug}}\n"


def test_template_headers_are_the_search_structure():
    for md in TEMPLATE.glob("*.md"):
        text = md.read_text(encoding="utf-8")
        assert text.startswith("Status: rascunho\nData: {{data}}\nTags:\n\n# "), md.name
        assert "/home/" not in text, md.name


@pytest.mark.parametrize(
    "slug", ["Artemis V2", "", "-acme", "acme-", "acme--v2", "acme_v2", "acme\n"]
)
def test_rejects_bad_slug(root: Path, slug: str):
    with pytest.raises(ValueError):
        new_project(slug, root, TODAY)

    assert not (root / "projects").exists()


def test_refuses_existing(root: Path):
    existing = root / "projects" / "acme-onboarding"
    existing.mkdir(parents=True)
    (existing / "notas.md").write_text("meu trabalho\n", encoding="utf-8")

    with pytest.raises(FileExistsError):
        new_project("acme-onboarding", root, TODAY)

    assert [p.name for p in existing.iterdir()] == ["notas.md"]


def test_cli_project_new_prints_the_created_path(root: Path, monkeypatch, capsys):
    monkeypatch.setenv("WS_REPO_ROOT", str(root))

    code = main(["project", "new", "acme-onboarding"])

    assert code == 0
    created = root / "projects" / "acme-onboarding"
    assert capsys.readouterr().out.strip() == str(created)
    assert (created / "README.md").is_file()


def test_cli_project_new_bad_slug_exits_one(root: Path, monkeypatch, capsys):
    monkeypatch.setenv("WS_REPO_ROOT", str(root))

    code = main(["project", "new", "Artemis V2"])

    assert code == 1
    assert "slug" in capsys.readouterr().err
    assert not (root / "projects").exists()


def test_cli_project_new_existing_exits_one(root: Path, monkeypatch, capsys):
    monkeypatch.setenv("WS_REPO_ROOT", str(root))
    (root / "projects" / "acme-onboarding").mkdir(parents=True)

    code = main(["project", "new", "acme-onboarding"])

    assert code == 1
    assert "acme-onboarding" in capsys.readouterr().err


def test_creates_the_local_data_folder_outside_the_repo(root: Path):
    new_project("acme-onboarding", root, TODAY)

    local = config.data_dir() / "projects" / "acme-onboarding"
    assert local.is_dir()
    assert local.stat().st_mode & 0o777 == 0o700


def test_an_existing_local_data_folder_is_kept(root: Path):
    local = config.data_dir() / "projects" / "acme-onboarding"
    local.mkdir(parents=True)
    (local / "run.log").write_text("kept\n", encoding="utf-8")

    new_project("acme-onboarding", root, TODAY)

    assert (local / "run.log").read_text(encoding="utf-8") == "kept\n"
