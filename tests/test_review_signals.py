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
    configured = RepoProfile(**{**p.__dict__, "helpers": ("env_str",)})
    settings = EnvCheckSettings("aws", None, (), {"acme-api": configured})
    assert profile_for("acme-api", tmp_path, settings).helpers == ("env_str",)
    assert profile_for("acme-front", tmp_path, settings).helpers == ()
