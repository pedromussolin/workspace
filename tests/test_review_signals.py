from dataclasses import replace
from pathlib import Path

from ws.envcheck import DEFAULT_EXCLUDE_GLOBS, EnvCheckSettings, RepoProfile
from ws.reviewsignals import env_report, migration_report, new_side, profile_for


def mig(revision, down):
    return f'revision = "{revision}"\ndown_revision = {down!r}\n'


B1 = "db/versions/b1.py"
B2 = "db/versions/b2.py"
C3 = "db/versions/c3.py"


def base_migs():
    return {B1: mig("b1", None), B2: mig("b2", "b1")}


def test_migration_report_new_migration_on_the_base_head():
    new = {**base_migs(), C3: mig("c3", "b2")}
    report, flags, warnings = migration_report(base_migs(), new)
    assert report["added"] == [{"path": C3, "revision": "c3", "down_revision": ["b2"]}]
    assert report["heads_before"] == ["b2"]
    assert report["heads_after"] == ["c3"]
    assert report["changed_existing"] == []
    assert flags == []
    assert warnings == []


def test_migration_report_flags_changed_and_deleted_existing():
    new = {B2: mig("b2", "b1") + "# edited\n"}
    report, flags, _ = migration_report(base_migs(), new)
    assert f"existing migration changed: {B2}" in flags
    assert f"existing migration deleted: {B1}" in flags
    assert B2 in report["changed_existing"]


def test_migration_report_flags_two_heads():
    new = {**base_migs(), C3: mig("c3", "b1")}
    report, flags, _ = migration_report(base_migs(), new)
    assert report["heads_after"] == ["b2", "c3"]
    assert "more than one Alembic head after the change: b2, c3" in flags


def test_migration_report_unreadable_is_a_warning():
    new = {**base_migs(), C3: "def broken(:\n", "db/versions/d4.py": mig("d4", "b2")}
    report, _, warnings = migration_report(base_migs(), new)
    assert len(warnings) == 1
    assert C3 in warnings[0]
    assert [a["revision"] for a in report["added"]] == ["d4"]


def plain(**overrides) -> RepoProfile:
    return (
        profile_for("acme-api", Path("/nowhere"), None)
        if not overrides
        else RepoProfile(
            **{**profile_for("acme-api", Path("/nowhere"), None).__dict__, **overrides}
        )
    )


def test_env_report_added_and_removed():
    base = {"app/a.py": b'import os\nx = os.environ["A"]\n'}
    new = {"app/a.py": b'import os\nx = os.environ["B"]\ny = os.getenv("C")\n'}
    report, flags, _ = env_report(base, new, plain(), {"app/a.py"})
    assert [(e["name"], e["required"]) for e in report["added"]] == [("B", True), ("C", False)]
    assert report["added"][0]["where"] == ["app/a.py:2"]
    assert report["removed"] == ["A"]
    assert flags == ["required env var added: B; check the Parameter Store"]


SETTINGS_BASE = (
    b"from pydantic_settings import BaseSettings\n\nclass Base(BaseSettings):\n    x: str = 'a'\n"
)


def test_env_report_settings_base_in_an_unchanged_file():
    base = {"core/base.py": SETTINGS_BASE}
    new = {
        "core/base.py": SETTINGS_BASE,
        "app/s.py": b"from core.base import Base\n\nclass S(Base):\n    lote_cutoff: str\n",
    }
    report, _, _ = env_report(base, new, plain(), {"app/s.py"})
    assert [e["name"] for e in report["added"]] == ["LOTE_CUTOFF"]


def test_env_report_uses_the_profile_helpers():
    new = {"app/a.py": b'x = env_str("D")\n'}
    report, _, _ = env_report({}, new, plain(helpers=("env_str",)), {"app/a.py"})
    assert [e["name"] for e in report["added"]] == ["D"]


def test_env_report_keeps_warnings_of_changed_paths_only():
    base = {"old/bad.py": b"def x(:\n"}
    new = {"old/bad.py": b"def x(:\n", "app/bad.py": b"def y(:\n"}
    _, _, warnings = env_report(base, new, plain(), {"app/bad.py"})
    assert warnings and all(w.startswith("app/bad.py") for w in warnings)


def test_new_side_overlays_the_work_tree(tmp_path):
    (tmp_path / "a.py").write_bytes(b"new a")
    (tmp_path / "sub").mkdir()
    (tmp_path / "sub" / "dir").mkdir()
    base = {"a.py": b"old a", "gone.py": b"x", "keep.py": b"k"}
    out = new_side(base, tmp_path, ["gone.py"], ["a.py", "missing.py", "sub/dir"])
    assert out == {"a.py": b"new a", "keep.py": b"k"}


def test_profile_for_falls_back_to_a_plain_profile(tmp_path):
    p = profile_for("acme-api", tmp_path, None)
    assert p.kind == "python"
    assert p.helpers == ()
    assert p.migration_globs == ()
    assert p.exclude_globs == DEFAULT_EXCLUDE_GLOBS
    configured = replace(p, helpers=("env_str",))
    settings = EnvCheckSettings("aws", None, (), {"acme-api": configured})
    assert profile_for("acme-api", tmp_path, settings).helpers == ("env_str",)
    assert profile_for("acme-front", tmp_path, settings).helpers == ()


def test_new_side_never_reads_outside_the_repo(tmp_path):
    outside = tmp_path / "outside"
    outside.mkdir()
    (outside / "secret.txt").write_bytes(b"secret")
    root = tmp_path / "repo"
    root.mkdir()
    (root / "docs").symlink_to(outside, target_is_directory=True)
    (root / "link.txt").symlink_to(outside / "secret.txt")
    (root / "ok.txt").write_bytes(b"ok")
    out = new_side({}, root, [], ["docs/secret.txt", "link.txt", "../outside/secret.txt", "ok.txt"])
    assert out == {"ok.txt": b"ok"}


def test_migration_report_merge_migration_with_a_tuple_down_revision():
    new = {**base_migs(), C3: mig("c3", "b1"), "db/versions/m4.py": mig("m4", ("b2", "c3"))}
    report, flags, _ = migration_report(base_migs(), new)
    merge = next(a for a in report["added"] if a["revision"] == "m4")
    assert merge["down_revision"] == ["b2", "c3"]
    assert report["heads_after"] == ["m4"]
    assert flags == []


def test_migration_report_a_renamed_migration_is_not_added():
    new = {B1: mig("b1", None), "db/versions/b2_renamed.py": mig("b2", "b1")}
    report, flags, _ = migration_report(base_migs(), new)
    assert report["added"] == []
    assert f"existing migration deleted: {B2}" in flags


def test_migration_report_warns_once_and_only_for_touched_paths():
    bad = "def broken(:\n"
    base = {**base_migs(), "db/versions/old_bad.py": bad}
    new = {**base, C3: bad}
    _, _, warnings = migration_report(base, new)
    assert len(warnings) == 1
    assert C3 in warnings[0]


def test_env_report_optional_to_required_is_added_and_flagged():
    base = {"app/a.py": b'import os\nx = os.getenv("A")\n'}
    new = {"app/a.py": b'import os\nx = os.environ["A"]\n'}
    report, flags, _ = env_report(base, new, plain(), {"app/a.py"})
    assert [(e["name"], e["required"]) for e in report["added"]] == [("A", True)]
    assert flags == ["required env var added: A; check the Parameter Store"]
    assert report["removed"] == []


def test_env_report_scans_the_shell_files():
    new = {"run.sh": b"echo ${SHELL_VAR}\n"}
    report, flags, _ = env_report({}, new, plain(shell_files=("run.sh",)), {"run.sh"})
    assert [(e["name"], e["required"]) for e in report["added"]] == [("SHELL_VAR", True)]
    assert flags == ["required env var added: SHELL_VAR; check the Parameter Store"]


def test_env_report_keeps_warnings_without_a_line_number():
    new = {"run.sh": b"echo hi\n"}
    _, _, warnings = env_report({}, new, plain(shell_files=("run.sh", "gone.sh")), {"gone.sh"})
    assert warnings == ["gone.sh: shell file not found at that commit"]
