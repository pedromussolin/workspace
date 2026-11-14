import os
import stat
from datetime import UTC, datetime, timedelta

from ws import approval

NOW = datetime(2026, 11, 13, 12, 0, tzinfo=UTC)
PREVIEW = "ws release preview"


def _record(created: datetime) -> dict:
    return {"code": "abc", "created_at": created.isoformat(), "sid": 1}


def _store(tmp_path):
    folder = tmp_path / "pending"
    approval.ensure_store(folder)
    return folder


def test_pending_roundtrip_is_private(tmp_path):
    folder = _store(tmp_path)
    approval.write_pending(folder, "abc", _record(NOW))
    assert stat.S_IMODE((folder / "abc.json").stat().st_mode) == 0o600
    assert stat.S_IMODE(folder.stat().st_mode) == 0o700
    record, reason = approval.read_pending(folder, "abc", now=NOW, preview=PREVIEW)
    assert reason is None
    assert record["sid"] == 1
    assert record["_created"] == NOW


def test_pending_absent(tmp_path):
    folder = _store(tmp_path)
    assert approval.read_pending(folder, "abc", now=NOW, preview=PREVIEW) == (None, None)


def test_pending_refused_when_not_private(tmp_path, monkeypatch):
    folder = _store(tmp_path)
    approval.write_pending(folder, "abc", _record(NOW))
    (folder / "abc.json").chmod(0o644)
    record, reason = approval.read_pending(folder, "abc", now=NOW, preview=PREVIEW)
    assert record is None
    assert "mode 600" in reason
    assert f"run {PREVIEW} again" in reason
    (folder / "abc.json").chmod(0o600)
    monkeypatch.setattr(os, "getuid", lambda: os.geteuid() + 1)
    record, reason = approval.read_pending(folder, "abc", now=NOW, preview=PREVIEW)
    assert record is None
    assert "mode 600" in reason


def test_pending_refused_when_in_the_future(tmp_path):
    folder = _store(tmp_path)
    approval.write_pending(folder, "abc", _record(NOW + timedelta(minutes=5)))
    record, reason = approval.read_pending(folder, "abc", now=NOW, preview=PREVIEW)
    assert record is None
    assert "in the future" in reason


def test_pending_unreadable(tmp_path):
    folder = _store(tmp_path)
    approval.write_pending(folder, "abc", {"code": "abc"})
    record, reason = approval.read_pending(folder, "abc", now=NOW, preview=PREVIEW)
    assert record is None
    assert "unreadable" in reason
    (folder / "abc.json").write_text("{", encoding="utf-8")
    assert approval.read_pending(folder, "abc", now=NOW, preview=PREVIEW)[1]


def test_write_removes_a_half_written_file(tmp_path):
    folder = _store(tmp_path)
    try:
        approval.write_pending(folder, "abc", {"bad": object()})
    except TypeError:
        pass
    assert not (folder / "abc.json").exists()


def test_purge_drops_expired_records(tmp_path):
    folder = _store(tmp_path)
    approval.write_pending(folder, "old", _record(NOW - timedelta(minutes=31)))
    approval.write_pending(folder, "new", _record(NOW - timedelta(minutes=5)))
    approval.purge_expired(folder, now=NOW, preview=PREVIEW)
    assert not (folder / "old.json").exists()
    assert (folder / "new.json").exists()


def test_digest_is_stable_and_12_hex():
    first = approval.digest({"b": 1, "a": "é"})
    assert first == approval.digest({"a": "é", "b": 1})
    assert approval.CODE.fullmatch(first)
    assert first != approval.digest({"a": "é", "b": 2})


def test_session_id_is_the_shells_session():
    assert approval.session_id() == os.getsid(0)
