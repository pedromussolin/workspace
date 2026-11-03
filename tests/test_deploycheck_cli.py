import pytest

from ws.cli import main


def test_deploy_check_stub_is_registered_and_not_implemented(capsys):
    """Step 0 stub; part D of the session automations replaces this file's tests with its own."""
    assert main(["deploy-check"]) == 2
    assert "ws deploy-check: not implemented yet" in capsys.readouterr().err


def test_deploy_check_stub_has_help():
    with pytest.raises(SystemExit) as exc:
        main(["deploy-check", "--help"])
    assert exc.value.code == 0
