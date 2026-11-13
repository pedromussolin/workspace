import subprocess
from pathlib import Path, PurePosixPath

import pytest
from adopt_items.relink import affected_files, rename_slug, rewrite_links

P = PurePosixPath


def test_link_in_a_moved_file_is_recomputed_for_a_stayed_target():
    out = rewrite_links(
        "see [d](../decisions.md)",
        P("projects/a/tasks/x.md"),
        P("projects/b/tasks/x.md"),
        {P("projects/a/tasks/x.md"): P("projects/b/tasks/x.md")},
    )
    assert out == "see [d](../../a/decisions.md)"


def test_link_to_a_moved_file_is_rewritten_in_a_file_that_stayed():
    out = rewrite_links(
        "![i](tasks/y.md) and [t](tasks/y.md)",
        P("projects/a/README.md"),
        P("projects/a/README.md"),
        {P("projects/a/tasks/y.md"): P("projects/b/tasks/y.md")},
    )
    assert out == "![i](../b/tasks/y.md) and [t](../b/tasks/y.md)"


def test_anchor_and_title_are_kept():
    out = rewrite_links(
        '[t](y.md#sec "t")',
        P("projects/a/README.md"),
        P("projects/a/README.md"),
        {P("projects/a/y.md"): P("projects/b/y.md")},
    )
    assert out == '[t](../b/y.md#sec "t")'


MOVED = {P("projects/a/y.md"): P("projects/b/y.md")}


@pytest.mark.parametrize(
    "text",
    [
        "[t](https://example.com/y.md)",
        "[t](mailto:y.md)",
        "[t](/abs/y.md)",
        "[t](#y.md)",
        "```\n[t](y.md)\n```",
        "`[t](y.md)`",
        "[t](z.md)",
        "the file y.md is in prose",
    ],
)
def test_not_rewritten(text):
    src = P("projects/a/README.md")
    assert rewrite_links(text, src, src, MOVED) == text


def test_text_after_a_fence_is_rewritten_again():
    src = P("projects/a/README.md")
    out = rewrite_links("```\n[t](y.md)\n```\n[t](y.md)", src, src, MOVED)
    assert out == "```\n[t](y.md)\n```\n[t](../b/y.md)"


def test_reference_style_definition_is_rewritten():
    src = P("projects/a/README.md")
    assert rewrite_links("[x]: y.md", src, src, MOVED) == "[x]: ../b/y.md"
    assert rewrite_links('[x]: y.md "t"', src, src, MOVED) == '[x]: ../b/y.md "t"'


def test_folder_prefix_move():
    out = rewrite_links(
        "[a](../operations-screens-migration/tasks/a.md)",
        P("projects/x/README.md"),
        P("projects/x/README.md"),
        {P("projects/operations-screens-migration"): P("projects/vm-migration")},
    )
    assert out == "[a](../vm-migration/tasks/a.md)"


def test_rename_slug_replaces_every_occurrence_and_only_the_slug():
    text = "operations-screens-migration/x and operations-screens-migration; operations screens"
    assert (
        rename_slug(text, "operations-screens-migration", "vm-migration")
        == "vm-migration/x and vm-migration; operations screens"
    )


def git(repo: Path, *args: str) -> None:
    subprocess.run(["git", "-C", str(repo), *args], check=True, capture_output=True)


def test_affected_files_skips_docs_history(tmp_path):
    git(tmp_path, "init", "-q")
    files = {
        "README.md": "[a](projects/a/y.md)",
        "projects/c/README.md": "[a](../a/y.md)",
        "projects/c/other.md": "nothing",
        "docs/specs/x.md": "[a](../../projects/a/y.md)",
        "projects/d/project.toml": "name = 'operations-screens-migration'",
    }
    for name, body in files.items():
        path = tmp_path / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(body)
    git(tmp_path, "add", ".")
    moved = {P("projects/a/y.md"): P("projects/b/y.md")}
    found = affected_files(tmp_path, moved)
    assert sorted(str(p.relative_to(tmp_path)) for p in found) == [
        "README.md",
        "projects/c/README.md",
        "projects/d/project.toml",
    ]
