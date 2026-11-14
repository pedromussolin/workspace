import pytest

from ws.cli import build_parser


def _parse(*argv):
    return build_parser().parse_args(["release", *argv])


def test_release_parser_fields():
    args = _parse("branches", "--project", "p", "--task", "TS-1", "TS-2", "--repo", "a")
    assert (args.project, args.tasks, args.repos, args.items) == ("p", ["TS-1", "TS-2"], ["a"], [])

    args = _parse("branches", "--project", "p", "--task", "TS-1", "--from-items", "x", "y")
    assert (args.items, args.repos) == (["x", "y"], [])

    args = _parse("new", "20261120", "--project", "p", "--repo", "a", "b")
    assert (args.day, args.repos, args.project) == ("20261120", ["a", "b"], "p")

    args = _parse("preview", "publish", "20261120", "--project", "p")
    assert (args.day, args.repos) == ("20261120", [])

    args = _parse(
        "preview", "move", "20261120", "20261127", "--reason", "atraso", "--delete-old-branches"
    )
    assert (args.old, args.new, args.reason, args.delete_old_branches) == (
        "20261120",
        "20261127",
        "atraso",
        True,
    )

    args = _parse("publish", "20261120", "--project", "p", "--approve", "abc123")
    assert (args.day, args.approve) == ("20261120", "abc123")

    args = _parse("move", "20261120", "20261127", "--reason", "r", "--approve", "abc123")
    assert (args.old, args.new, args.approve, args.delete_old_branches) == (
        "20261120",
        "20261127",
        "abc123",
        False,
    )

    args = _parse("status", "--project", "p", "--links")
    assert (args.day, args.links) == (None, True)
    assert _parse("status", "20261120", "--project", "p").day == "20261120"


def test_release_parser_refuses_abbreviations(capsys):
    with pytest.raises(SystemExit) as stop:
        _parse("publish", "20261120", "--project", "p", "--appr", "x")
    assert stop.value.code == 2
    with pytest.raises(SystemExit):
        _parse("move", "a", "b", "--reason", "r", "--appr", "x")


def test_release_handlers_import_lazily(monkeypatch):
    import sys
    import types

    calls = []
    for name, func in [
        ("branches", "run_branches"),
        ("build", "run_new"),
        ("publish", "run_preview"),
        ("move", "run_preview"),
        ("status", "run_status"),
    ]:
        module = types.ModuleType(f"ws.release.{name}")
        setattr(module, func, lambda args, n=name, f=func: calls.append((n, f)) or 0)
        monkeypatch.setitem(sys.modules, f"ws.release.{name}", module)
    sys.modules["ws.release.publish"].run_publish = lambda args: (
        calls.append(("publish", "run_publish")) or 0
    )
    sys.modules["ws.release.move"].run_move = lambda args: calls.append(("move", "run_move")) or 0
    import ws.release as release

    for name in ("branches", "build", "publish", "move", "status"):
        monkeypatch.setattr(release, name, sys.modules[f"ws.release.{name}"], raising=False)

    for argv in (
        ["branches", "--task", "TS-1"],
        ["new", "20261120"],
        ["preview", "publish", "20261120"],
        ["preview", "move", "a", "b", "--reason", "r"],
        ["publish", "20261120", "--approve", "x"],
        ["move", "a", "b", "--reason", "r", "--approve", "x"],
        ["status"],
    ):
        args = _parse(*argv, "--project", "p")
        assert args.handler(args) == 0

    assert [c[1] for c in calls] == [
        "run_branches",
        "run_new",
        "run_preview",
        "run_preview",
        "run_publish",
        "run_move",
        "run_status",
    ]
