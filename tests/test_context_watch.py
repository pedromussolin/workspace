import importlib.util
import io
import json
import os
import subprocess
import sys
import time
from pathlib import Path

import pytest

HOOK = Path(__file__).resolve().parents[1] / "hooks" / "context_watch.py"
SPEC = importlib.util.spec_from_file_location("context_watch", HOOK)
context_watch = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(context_watch)

SESSION = "abc-123"


def entry(
    tokens: int = 0,
    *,
    fresh: int | None = None,
    created: int = 0,
    cached: int = 0,
    sidechain: bool = False,
    model: str = "claude-model",
    kind: str = "assistant",
    padding: int = 0,
) -> dict:
    fresh = tokens if fresh is None else fresh
    return {
        "type": kind,
        "isSidechain": sidechain,
        "message": {
            "model": model,
            "content": "x" * padding,
            "usage": {
                "input_tokens": fresh,
                "cache_creation_input_tokens": created,
                "cache_read_input_tokens": cached,
                "output_tokens": 5000,
            },
        },
    }


def transcript(tmp_path: Path, entries: list, name: str = "t.jsonl") -> Path:
    path = tmp_path / name
    path.write_text("".join(json.dumps(item) + "\n" for item in entries), encoding="utf-8")
    return path


@pytest.fixture
def env(tmp_path, monkeypatch):
    monkeypatch.setenv("WS_CACHE_DIR", str(tmp_path / "cache"))
    monkeypatch.setenv("WS_CONFIG_DIR", str(tmp_path / "config"))
    (tmp_path / "config").mkdir()
    return tmp_path


def run_hook(payload, tmp_path: Path, raw: str | None = None) -> subprocess.CompletedProcess[str]:
    environment = {
        **os.environ,
        "WS_CACHE_DIR": str(tmp_path / "cache"),
        "WS_CONFIG_DIR": str(tmp_path / "config"),
    }
    return subprocess.run(
        [sys.executable, "-I", "-B", str(HOOK)],
        input=json.dumps(payload) if raw is None else raw,
        capture_output=True,
        text=True,
        check=False,
        env=environment,
    )


def prompt(tmp_path: Path, tokens: int, session: str = SESSION) -> subprocess.CompletedProcess[str]:
    path = transcript(tmp_path, [entry(tokens)])
    return run_hook({"session_id": session, "transcript_path": str(path)}, tmp_path)


def test_tokens_sum_input_and_cache_fields(tmp_path):
    path = transcript(tmp_path, [entry(fresh=10, created=2_000, cached=300_000)])

    assert context_watch.context_tokens(path) == 302_010


def test_skips_sidechain_and_synthetic_entries(tmp_path):
    path = transcript(
        tmp_path,
        [
            entry(111_000),
            entry(900_000, sidechain=True),
            entry(800_000, model="<synthetic>"),
            entry(0),
            entry(700_000, kind="user"),
        ],
    )

    assert context_watch.context_tokens(path) == 111_000


def test_returns_none_without_a_usable_entry(tmp_path):
    path = transcript(tmp_path, [entry(5, kind="user"), {"type": "summary"}])
    path.write_text(path.read_text(encoding="utf-8") + "not json\n", encoding="utf-8")

    assert context_watch.context_tokens(path) is None


def test_reads_a_last_line_over_one_chunk(tmp_path):
    big = entry(222_000, padding=3 << 20)
    path = transcript(tmp_path, [entry(1), big])

    assert path.stat().st_size > 3 << 20
    assert context_watch.context_tokens(path) == 222_000


def test_reads_past_a_big_line_without_usage(tmp_path):
    path = transcript(tmp_path, [entry(333_000), {"type": "user", "text": "y" * (3 << 20)}])

    assert context_watch.context_tokens(path) == 333_000


def test_stops_after_max_bytes(tmp_path):
    path = transcript(tmp_path, [entry(5_000), {"type": "user", "text": "y" * 4000}])

    assert context_watch.context_tokens(path, max_bytes=1000) is None
    assert context_watch.context_tokens(path) == 5_000


def test_missing_transcript_gives_no_output(tmp_path):
    result = run_hook(
        {"session_id": SESSION, "transcript_path": str(tmp_path / "nope.jsonl")}, tmp_path
    )

    assert result.returncode == 0 and result.stdout == ""
    assert not (tmp_path / "cache" / "hooks" / "errors.log").exists()


def test_band_function():
    assert context_watch.band(299_999, 300_000, 100_000) == 0
    assert context_watch.band(300_000, 300_000, 100_000) == 1
    assert context_watch.band(399_999, 300_000, 100_000) == 1
    assert context_watch.band(400_000, 300_000, 100_000) == 2


def test_warns_once_per_band(tmp_path):
    outputs = [prompt(tmp_path, tokens).stdout for tokens in (250_000, 310_000, 320_000, 410_000)]
    outputs.append(prompt(tmp_path, 415_000).stdout)

    assert [bool(out) for out in outputs] == [False, True, False, True, False]


def test_band_resets_when_context_drops(tmp_path):
    outputs = [prompt(tmp_path, tokens).stdout for tokens in (310_000, 50_000, 310_000)]

    assert [bool(out) for out in outputs] == [True, False, True]


def test_sessions_do_not_share_bands(tmp_path):
    first = prompt(tmp_path, 310_000, session="one").stdout
    second = prompt(tmp_path, 310_000, session="two").stdout

    assert first and second


def test_bad_session_id_is_ignored(tmp_path):
    path = transcript(tmp_path, [entry(500_000)])

    for session in ("../x", "a/b", "", "x" * 65, "a b", 7, None):
        result = run_hook({"session_id": session, "transcript_path": str(path)}, tmp_path)
        assert result.returncode == 0 and result.stdout == ""
    assert not (tmp_path / "cache").exists()


def test_output_has_additional_context_and_user_notice(tmp_path):
    result = prompt(tmp_path, 312_345)

    answer = json.loads(result.stdout)
    context = answer["hookSpecificOutput"]
    assert context["hookEventName"] == "UserPromptSubmit"
    assert "312k tokens" in context["additionalContext"]
    assert "handoff" in context["additionalContext"]
    assert "do not compact" in context["additionalContext"]
    assert answer["systemMessage"] == (
        "Contexto em 312 mil tokens: o Claude vai propor um handoff na próxima pausa."
    )
    assert len(context["additionalContext"].split()) < 80


def test_user_notice_can_be_switched_off(env, monkeypatch):
    monkeypatch.setattr(context_watch, "USER_NOTICE", False)

    assert "systemMessage" not in context_watch._output(310_000)
    assert "hookSpecificOutput" in context_watch._output(310_000)


def _stdin(monkeypatch, payload) -> None:
    monkeypatch.setattr(sys, "stdin", io.StringIO(json.dumps(payload)))


def test_exception_exits_0_silently_and_logs(env, monkeypatch, capsys):
    path = transcript(env, [entry(500_000)])
    _stdin(monkeypatch, {"session_id": SESSION, "transcript_path": str(path)})

    def explode(*args, **kwargs):
        raise RuntimeError("secret detail that must not be logged")

    monkeypatch.setattr(context_watch, "context_tokens", explode)

    assert context_watch.main() == 0

    assert capsys.readouterr().out == ""
    log = (env / "cache" / "hooks" / "errors.log").read_text(encoding="utf-8")
    [line] = log.splitlines()
    assert line.endswith(" context_watch RuntimeError")
    assert "secret" not in log


def test_invalid_json_exits_0_silently_and_logs(env):
    result = run_hook(None, env, raw="not json")

    assert result.returncode == 0 and result.stdout == ""
    assert "context_watch JSONDecodeError" in (env / "cache" / "hooks" / "errors.log").read_text(
        encoding="utf-8"
    )


def test_deadline_exits_0_silently(env, monkeypatch, capsys):
    path = transcript(env, [entry(500_000)])
    _stdin(monkeypatch, {"session_id": SESSION, "transcript_path": str(path)})
    monkeypatch.setattr(context_watch, "DEADLINE", 0.2)
    monkeypatch.setattr(context_watch, "context_tokens", lambda *a, **k: time.sleep(5))

    started = time.monotonic()
    assert context_watch.main() == 0

    assert time.monotonic() - started < 3
    assert capsys.readouterr().out == ""
    assert "context_watch Deadline" in (env / "cache" / "hooks" / "errors.log").read_text(
        encoding="utf-8"
    )


def test_error_log_keeps_the_last_200_lines(env):
    for index in range(230):
        context_watch.log_error(f"E{index}")

    lines = (env / "cache" / "hooks" / "errors.log").read_text(encoding="utf-8").splitlines()
    assert len(lines) == 200
    assert lines[-1].endswith("E229") and lines[0].endswith("E30")


def test_no_usage_in_big_transcript_is_logged(env):
    path = env / "big.jsonl"
    path.write_text(
        "".join(json.dumps({"type": "user", "text": "z" * 1000}) + "\n" for _ in range(1500)),
        encoding="utf-8",
    )
    assert path.stat().st_size > 1 << 20
    payload = {"session_id": SESSION, "transcript_path": str(path)}

    first = run_hook(payload, env)
    second = run_hook(payload, env)

    assert first.stdout == "" and second.stdout == ""
    log = (env / "cache" / "hooks" / "errors.log").read_text(encoding="utf-8")
    assert log.count("context_watch no-usage") == 1


def test_no_usage_in_a_small_transcript_is_not_logged(env):
    path = transcript(env, [entry(5, kind="user")])

    run_hook({"session_id": SESSION, "transcript_path": str(path)}, env)

    assert not (env / "cache" / "hooks" / "errors.log").exists()


def test_config_overrides_warn_at_and_step(env):
    (env / "config" / "config.toml").write_text(
        "[context_watch]\nwarn_at = 1000\nstep = 500\n", encoding="utf-8"
    )

    outputs = [prompt(env, tokens).stdout for tokens in (900, 1000, 1400, 1500)]

    assert [bool(out) for out in outputs] == [False, True, False, True]


def test_invalid_config_means_the_defaults(env):
    (env / "config" / "config.toml").write_text(
        '[context_watch]\nwarn_at = "soon"\nstep = -1\n', encoding="utf-8"
    )

    assert prompt(env, 299_000).stdout == ""
    assert prompt(env, 301_000).stdout != ""
    (env / "config" / "config.toml").write_text("[context_watch\n", encoding="utf-8")
    assert prompt(env, 405_000).stdout != ""


def test_old_state_files_are_removed_once_a_day(env):
    folder = env / "cache" / "context-watch"
    folder.mkdir(parents=True)
    old = folder / "old-session.json"
    old.write_text("{}", encoding="utf-8")
    stamp = time.time() - 8 * 24 * 3600
    os.utime(old, (stamp, stamp))
    fresh = folder / "fresh-session.json"
    fresh.write_text("{}", encoding="utf-8")

    prompt(env, 310_000)

    assert not old.exists() and fresh.exists()
    again = folder / "old-again.json"
    again.write_text("{}", encoding="utf-8")
    os.utime(again, (stamp, stamp))
    prompt(env, 410_000)
    assert again.exists()


def test_the_hook_does_not_import_ws():
    source = HOOK.read_text(encoding="utf-8")

    assert "import ws" not in source and "from ws" not in source
