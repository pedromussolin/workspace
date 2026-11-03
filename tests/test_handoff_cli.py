import pytest

from ws.cli import main


def test_handoff_stub_is_registered_and_not_implemented(capsys):
    """Step 0 stub; part A of the session automations replaces this file's tests with its own."""
    assert main(["handoff"]) == 2
    assert "ws handoff: not implemented yet" in capsys.readouterr().err


def test_handoff_stub_has_help():
    with pytest.raises(SystemExit) as exc:
        main(["handoff", "--help"])
    assert exc.value.code == 0
