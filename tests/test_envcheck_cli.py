import pytest

from ws.cli import main


def test_env_stub_is_registered_and_not_implemented(capsys):
    """Step 0 stub; part C of the session automations replaces this file's tests with its own."""
    assert main(["env"]) == 2
    assert "ws env: not implemented yet" in capsys.readouterr().err


def test_env_stub_has_help():
    with pytest.raises(SystemExit) as exc:
        main(["env", "--help"])
    assert exc.value.code == 0
