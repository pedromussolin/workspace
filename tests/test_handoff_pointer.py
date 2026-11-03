import importlib.util
import json
import os
import subprocess
import sys
import time
from datetime import UTC, datetime
from pathlib import Path

import pytest

from ws import handoff

HOOK = Path(__file__).resolve().parents[1] / "hooks" / "handoff_pointer.py"
SPEC = importlib.util.spec_from_file_location("handoff_pointer", HOOK)
handoff_pointer = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(handoff_pointer)

DAY = 86400


@pytest.fixture
def env(tmp_path, monkeypatch):
    monkeypatch.setenv("WS_DATA_DIR", str(tmp_path / "data"))
    monkeypatch.setenv("WS_CONFIG_DIR", str(tmp_path / "config"))
    monkeypatch.setenv("WS_CACHE_DIR", str(tmp_path / "cache"))
    (tmp_path / "config").mkdir()
    return tmp_path


def make(folder: Path, name: str, title: str, age_days: float = 0.1, extra: str = "") -> Path:
    folder.mkdir(parents=True, exist_ok=True)
    path = folder / name
    path.write_text(f"{title}\n{extra}\nbody that must never be printed\n", encoding="utf-8")
    stamp = time.time() - age_days * DAY
    os.utime(path, (stamp, stamp))
    return path


def run_hook(tmp_path: Path, stdin: str = "{}") -> subprocess.CompletedProcess[str]:
    environment = {
        **os.environ,
        "WS_DATA_DIR": str(tmp_path / "data"),
        "WS_CONFIG_DIR": str(tmp_path / "config"),
        "WS_CACHE_DIR": str(tmp_path / "cache"),
    }
    return subprocess.run(
        [sys.executable, "-I", "-B", str(HOOK)],
        input=stdin,
        capture_output=True,
        text=True,
        check=False,
        env=environment,
    )


def context(result: subprocess.CompletedProcess[str]) -> str:
    answer = json.loads(result.stdout)["hookSpecificOutput"]
    assert answer["hookEventName"] == "SessionStart"
    return answer["additionalContext"]


def test_lists_newest_three_within_seven_days(env):
    folder = env / "data" / "projects" / "demo"
    for index, age in enumerate((1, 2, 3, 4, 20)):
        make(
            folder,
            f"HANDOFF-2026110{index}-t{index}.md",
            f"# Handoff 0{index}/11/2026: t{index}",
            age,
        )

    result = run_hook(env)

    lines = context(result).splitlines()
    assert result.returncode == 0
    assert len(lines) == 4
    assert [Path(line.split(" ")[1]).name for line in lines[1:]] == [
        "HANDOFF-20261100-t0.md",
        "HANDOFF-20261101-t1.md",
        "HANDOFF-20261102-t2.md",
    ]
    assert "t4" not in context(result) and "t3" not in context(result)


def test_skips_closed_handoffs(env):
    folder = env / "data" / "projects" / "demo"
    make(folder, "HANDOFF-20261103-a.md", "# Handoff 03/11/2026: a", extra="Status: encerrado")
    make(folder, "HANDOFF-20261103-b.md", "# Handoff 03/11/2026: b")

    text = context(run_hook(env))

    assert "-b.md" in text and "-a.md" not in text


def test_reads_extra_globs(env):
    legacy = env / "legacy"
    make(legacy, "HANDOFF-20261102-old.md", "# Handoff 02/11/2026: legado")
    (env / "config" / "config.toml").write_text(
        f'[handoff]\nextra_globs = ["{legacy}/HANDOFF-*.md"]\nmax_listed = 5\n', encoding="utf-8"
    )

    text = context(run_hook(env))

    assert "HANDOFF-20261102-old.md" in text and "legado" in text


def test_config_age_and_count_apply(env):
    folder = env / "data" / "projects" / "demo"
    make(folder, "HANDOFF-20261101-a.md", "# Handoff: a", age_days=3)
    make(folder, "HANDOFF-20261102-b.md", "# Handoff: b", age_days=0.2)
    (env / "config" / "config.toml").write_text(
        "[handoff]\nmax_age_days = 1\nmax_listed = 1\n", encoding="utf-8"
    )

    text = context(run_hook(env))

    assert "-b.md" in text and "-a.md" not in text


def test_invalid_config_means_the_defaults(env):
    make(env / "data" / "projects" / "demo", "HANDOFF-20261103-a.md", "# Handoff: a")
    (env / "config" / "config.toml").write_text(
        '[handoff]\nextra_globs = "x"\nmax_age_days = "a"\nmax_listed = 0\n', encoding="utf-8"
    )

    assert "-a.md" in context(run_hook(env))


def test_output_is_paths_and_titles_only(env):
    make(env / "data" / "projects" / "demo", "HANDOFF-20261103-a.md", "# Handoff 03/11/2026: tema")

    text = context(run_hook(env))

    assert "body that must never be printed" not in text
    assert text.splitlines()[0].startswith("Recent handoffs (newest first)")
    assert text.splitlines()[1].endswith("): Handoff 03/11/2026: tema")


def test_output_under_budget(env):
    folder = env / "data" / "projects" / "demo"
    for index in range(6):
        make(folder, f"HANDOFF-2026110{index}-x.md", "# " + "T" * 300, age_days=index / 10 + 0.1)

    lines = context(run_hook(env)).splitlines()

    assert len(lines) <= 4
    for line in lines[1:]:
        title = line.split("): ", 1)[1]
        assert len(title) <= 120


def test_nothing_found_no_output(env):
    result = run_hook(env)

    assert result.returncode == 0 and result.stdout == ""
    make(env / "data" / "projects" / "demo", "HANDOFF-20261001-a.md", "# old", age_days=30)
    assert run_hook(env).stdout == ""


def test_error_exits_0_silently(env, monkeypatch, capsys):
    def explode(*args, **kwargs):
        raise OSError("secret detail")

    monkeypatch.setattr(handoff_pointer, "recent_handoffs", explode)

    assert handoff_pointer.main() == 0

    assert capsys.readouterr().out == ""
    log = (env / "cache" / "hooks" / "errors.log").read_text(encoding="utf-8")
    assert log.splitlines()[-1].endswith(" handoff_pointer OSError")
    assert "secret" not in log


def test_deadline_exits_0_silently(env, monkeypatch, capsys):
    monkeypatch.setattr(handoff_pointer, "DEADLINE", 0.2)
    monkeypatch.setattr(handoff_pointer, "recent_handoffs", lambda *a, **k: time.sleep(5))

    started = time.monotonic()
    assert handoff_pointer.main() == 0

    assert time.monotonic() - started < 3
    assert capsys.readouterr().out == ""
    assert "handoff_pointer Deadline" in (env / "cache" / "hooks" / "errors.log").read_text(
        encoding="utf-8"
    )


def test_pointer_and_find_handoffs_agree(env):
    folder = env / "data" / "projects" / "demo"
    legacy = env / "legacy"
    make(folder, "HANDOFF-20261101-a.md", "# Handoff 01/11/2026: a", age_days=2)
    make(folder, "HANDOFF-20261102-b.md", "# Handoff 02/11/2026: b", age_days=1)
    make(folder, "HANDOFF-20261103-c.md", "# Handoff 03/11/2026: c", extra="Status: encerrado")
    make(legacy, "HANDOFF-20261031-d.md", "# Handoff 31/10/2026: d", age_days=3)
    make(legacy, "HANDOFF-20261020-e.md", "# Handoff 20/10/2026: e", age_days=14)
    globs = [str(legacy / "HANDOFF-*.md")]
    now = time.time()

    pointed = handoff_pointer.recent_handoffs(env / "data", globs, limit=3, max_age_days=7, now=now)
    found = handoff.find_handoffs(
        env / "data",
        globs,
        limit=3,
        max_age_days=7,
        now=datetime.fromtimestamp(now, UTC),
    )

    assert [str(path) for path, _, _ in pointed] == [item["path"] for item in found]
    assert [title for _, _, title in pointed] == [item["title"] for item in found]
    assert len(pointed) == 3


def test_the_hook_does_not_import_ws():
    source = HOOK.read_text(encoding="utf-8")

    assert "import ws" not in source and "from ws" not in source
