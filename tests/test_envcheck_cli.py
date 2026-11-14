import pytest

from ws.cli import main


def test_env_needs_a_subcommand(capsys):
    with pytest.raises(SystemExit) as exc:
        main(["env"])
    assert exc.value.code == 2
    assert "check" in capsys.readouterr().err


def test_env_has_help(capsys):
    with pytest.raises(SystemExit) as exc:
        main(["env", "--help"])
    assert exc.value.code == 0
    assert "check" in capsys.readouterr().out


def test_env_check_help_lists_its_flags(capsys):
    with pytest.raises(SystemExit) as exc:
        main(["env", "check", "--help"])
    assert exc.value.code == 0
    out = capsys.readouterr().out
    for flag in ("--env", "--ref", "--deployed", "--strict", "--json"):
        assert flag in out


def test_env_check_needs_an_environment(capsys):
    with pytest.raises(SystemExit) as exc:
        main(["env", "check", "api", "--ref", "HEAD"])
    assert exc.value.code == 2
    assert "--env" in capsys.readouterr().err
